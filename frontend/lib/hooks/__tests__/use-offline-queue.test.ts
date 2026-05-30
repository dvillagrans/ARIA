// fake-indexeddb/auto MUST be the first import — patches globalThis before idb loads.
import "fake-indexeddb/auto";

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  _resetDBForTesting,
  clear,
  enqueue,
  markInFlight,
} from "../../idb/message-queue";
import { useOfflineQueue } from "../use-offline-queue";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setNavigatorOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", {
    get: () => value,
    configurable: true,
  });
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(async () => {
  // Reset the IDB singleton so fake-indexeddb's fresh instance is used.
  _resetDBForTesting();
  await clear();
  setNavigatorOnline(true);
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// 3.5 — isOnline reflects navigator.onLine
// ---------------------------------------------------------------------------
describe("isOnline", () => {
  it("reflects navigator.onLine=true on mount", async () => {
    setNavigatorOnline(true);
    const { result } = renderHook(() => useOfflineQueue());
    // Wait for effects to settle.
    await act(async () => {});
    expect(result.current.isOnline).toBe(true);
  });

  it("reflects navigator.onLine=false on mount", async () => {
    setNavigatorOnline(false);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});
    expect(result.current.isOnline).toBe(false);
  });

  it("sets isOnline false on offline event", async () => {
    setNavigatorOnline(true);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    await act(async () => {
      setNavigatorOnline(false);
      window.dispatchEvent(new Event("offline"));
    });
    expect(result.current.isOnline).toBe(false);
  });

  it("sets isOnline true on online event", async () => {
    setNavigatorOnline(false);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    // Mock fetch to resolve immediately so drain doesn't hang.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ confirmation_text: "ok" }) })
    );

    await act(async () => {
      setNavigatorOnline(true);
      window.dispatchEvent(new Event("online"));
    });
    expect(result.current.isOnline).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3.6 — enqueueMessage increments pendingCount / mount-time in-flight reset
// ---------------------------------------------------------------------------
describe("enqueueMessage", () => {
  it("increments pendingCount", async () => {
    setNavigatorOnline(false);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    expect(result.current.pendingCount).toBe(0);

    await act(async () => {
      await result.current.enqueueMessage("Hi");
    });
    expect(result.current.pendingCount).toBe(1);

    await act(async () => {
      await result.current.enqueueMessage("Hello");
    });
    expect(result.current.pendingCount).toBe(2);
  });
});

describe("mount-time in-flight reset", () => {
  it("resets in-flight items to pending on mount", async () => {
    // Seed IDB with an in-flight item directly (simulate a crashed previous session).
    const msg = await enqueue("abandoned");
    await markInFlight(msg.id);

    // Mount hook — it should reset in-flight → pending.
    const { result } = renderHook(() => useOfflineQueue());

    // Wait for the async initFromIDB effect to fully complete.
    await waitFor(() => {
      expect(result.current.pendingCount).toBe(1);
    });
  });
});

// ---------------------------------------------------------------------------
// 3.7 — drain scenarios
// ---------------------------------------------------------------------------
describe("drainQueue", () => {
  it("sequential drain: A sent before B, both removed, pendingCount=0", async () => {
    setNavigatorOnline(false);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    await act(async () => {
      await result.current.enqueueMessage("A");
    });
    // Small delay to ensure distinct queuedAt timestamps for stable ordering.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2));
      await result.current.enqueueMessage("B");
    });
    expect(result.current.pendingCount).toBe(2);

    const sentOrder: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((_url: string, opts: RequestInit) => {
        const body = JSON.parse(opts.body as string);
        sentOrder.push(body.message);
        return Promise.resolve({
          ok: true,
          json: async () => ({ confirmation_text: "ok" }),
        });
      })
    );

    const onSent = vi.fn();
    const onFailed = vi.fn();

    await act(async () => {
      await result.current.drainQueue(onSent, onFailed);
    });

    expect(sentOrder).toEqual(["A", "B"]);
    expect(onSent).toHaveBeenCalledTimes(2);
    expect(onFailed).not.toHaveBeenCalled();
    expect(result.current.pendingCount).toBe(0);
  });

  it("failure isolation: A fails → stays pending, B still attempted", async () => {
    setNavigatorOnline(false);
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    await act(async () => {
      await result.current.enqueueMessage("A");
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2));
      await result.current.enqueueMessage("B");
    });

    let callCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error("network failure"));
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ confirmation_text: "ok" }),
        });
      })
    );

    const onSent = vi.fn();
    const onFailed = vi.fn();

    await act(async () => {
      await result.current.drainQueue(onSent, onFailed);
    });

    expect(onFailed).toHaveBeenCalledTimes(1);
    expect(onSent).toHaveBeenCalledTimes(1);
    // A failed → 1 pending remains.
    expect(result.current.pendingCount).toBe(1);
  });

  it("multi-tab guard: in-flight items are skipped by drain", async () => {
    // Seed an in-flight item directly (simulating another tab marked it).
    // Mount first to reset any pre-existing in-flight items, but then add
    // a fresh in-flight item AFTER mount (to simulate another tab's action).
    const { result } = renderHook(() => useOfflineQueue());
    await act(async () => {});

    // Add a pending item normally via enqueueMessage.
    setNavigatorOnline(false);
    await act(async () => {
      await result.current.enqueueMessage("pending-one");
    });

    // Directly set an in-flight record in IDB (another tab scenario).
    const inFlight = await enqueue("in-flight-other-tab");
    await markInFlight(inFlight.id);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ confirmation_text: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const onSent = vi.fn();
    const onFailed = vi.fn();

    await act(async () => {
      await result.current.drainQueue(onSent, onFailed);
    });

    // Only the pending item should be fetched — in-flight is skipped.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.message).toBe("pending-one");
  });
});
