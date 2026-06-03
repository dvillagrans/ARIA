/**
 * useReminderPoll — polling interval optimization tests.
 *
 * Verifies that:
 * 1. The poll interval is 120 seconds (not the old 60s).
 * 2. The hook fetches on mount immediately.
 * 3. New reminders are shown, duplicates are filtered.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReminderPoll } from "../use-reminder-poll";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_REMINDERS = [
  { id: "r1", title: "Pay rent", due_at: "2026-06-01T10:00:00Z" },
  { id: "r2", title: "Call dentist", due_at: "2026-06-01T14:00:00Z" },
];

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useReminderPoll", () => {
  it("fetches reminders immediately on mount", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_REMINDERS),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReminderPoll());

    // Flush microtasks (the fetch promise).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/reminders/due");
    expect(result.current.dueReminders).toHaveLength(2);
  });

  it("uses 120-second polling interval (not 60s)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_REMINDERS),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useReminderPoll());

    // Flush initial fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const initialCalls = fetchMock.mock.calls.length;

    // Advance by 60 seconds — should NOT trigger a new fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(fetchMock.mock.calls.length).toBe(initialCalls);

    // Advance to 120 seconds — SHOULD trigger a new fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(fetchMock.mock.calls.length).toBe(initialCalls + 1);
  });

  it("filters duplicate reminders across polls", async () => {
    let callCount = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_REMINDERS),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve([
            ...MOCK_REMINDERS,
            { id: "r3", title: "New task", due_at: "2026-06-02T09:00:00Z" },
          ]),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReminderPoll());

    // Flush initial fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.dueReminders).toHaveLength(2);

    // Advance to trigger second poll.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(result.current.dueReminders).toHaveLength(3);

    // Verify no duplicates.
    const ids = result.current.dueReminders.map((r) => r.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("acknowledge removes reminder optimistically", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_REMINDERS),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReminderPoll());

    // Flush initial fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.dueReminders).toHaveLength(2);

    // Mock the acknowledge POST.
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "acknowledged" }),
    });

    // Use a separate act for the synchronous acknowledge call.
    act(() => {
      result.current.acknowledge("r1");
    });

    // Optimistic removal — should be immediate.
    expect(result.current.dueReminders).toHaveLength(1);
    expect(result.current.dueReminders[0].id).toBe("r2");
  });

  it("dismiss removes reminder from UI", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_REMINDERS),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReminderPoll());

    // Flush initial fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.dueReminders).toHaveLength(2);

    act(() => {
      result.current.dismiss("r1");
    });

    expect(result.current.dueReminders).toHaveLength(1);
    expect(result.current.dueReminders[0].id).toBe("r2");
  });

  it("silently handles fetch errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error"))
    );

    const { result } = renderHook(() => useReminderPoll());

    // Flush — should not throw.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.dueReminders).toHaveLength(0);
  });

  it("cleans up interval on unmount", async () => {
    const clearIntervalSpy = vi.spyOn(global, "clearInterval");

    const { unmount } = renderHook(() => useReminderPoll());

    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
