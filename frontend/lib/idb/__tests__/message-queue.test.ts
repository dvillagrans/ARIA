// fake-indexeddb/auto MUST be the first import — patches globalThis before idb loads.
import "fake-indexeddb/auto";

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  _resetDBForTesting,
  clear,
  enqueue,
  getAll,
  markInFlight,
  markPending,
  remove,
} from "../message-queue";

// Reset store state between tests.
beforeEach(async () => {
  _resetDBForTesting();
  await clear();
});

// ---------------------------------------------------------------------------
// 3.1 — Schema initialised on first open
// ---------------------------------------------------------------------------
describe("schema", () => {
  it("initialises the store on first call", async () => {
    // Any call (e.g. getAll) should not throw — store must exist.
    const items = await getAll();
    expect(Array.isArray(items)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3.2 — enqueue / getAll
// ---------------------------------------------------------------------------
describe("enqueue", () => {
  it("returns a QueuedMessage with status pending, unique id, correct text and timestamp", async () => {
    const before = Date.now();
    const msg = await enqueue("Hello");
    const after = Date.now();

    expect(msg.text).toBe("Hello");
    expect(msg.status).toBe("pending");
    expect(typeof msg.id).toBe("string");
    expect(msg.id.length).toBeGreaterThan(0);
    expect(msg.queuedAt).toBeGreaterThanOrEqual(before);
    expect(msg.queuedAt).toBeLessThanOrEqual(after);
  });

  it("generates unique ids for multiple enqueues", async () => {
    const a = await enqueue("A");
    const b = await enqueue("B");
    expect(a.id).not.toBe(b.id);
  });
});

describe("getAll", () => {
  it("returns records ordered by queuedAt ascending", async () => {
    // Enqueue sequentially; each enqueue calls Date.now() which advances.
    const a = await enqueue("first");
    // Small delay to guarantee distinct timestamps in fast environments.
    await new Promise((r) => setTimeout(r, 2));
    const b = await enqueue("second");
    await new Promise((r) => setTimeout(r, 2));
    const c = await enqueue("third");

    const items = await getAll();
    expect(items.map((i) => i.id)).toEqual([a.id, b.id, c.id]);
  });

  it("returns empty array when store is empty", async () => {
    const items = await getAll();
    expect(items).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 3.3 — markInFlight / markPending / remove / clear
// ---------------------------------------------------------------------------
describe("markInFlight", () => {
  it("sets status to in-flight", async () => {
    const msg = await enqueue("test");
    await markInFlight(msg.id);
    const items = await getAll();
    const updated = items.find((i) => i.id === msg.id);
    expect(updated?.status).toBe("in-flight");
  });
});

describe("markPending", () => {
  it("resets status back to pending", async () => {
    const msg = await enqueue("test");
    await markInFlight(msg.id);
    await markPending(msg.id);
    const items = await getAll();
    const updated = items.find((i) => i.id === msg.id);
    expect(updated?.status).toBe("pending");
  });
});

describe("remove", () => {
  it("deletes a single record by id", async () => {
    const a = await enqueue("A");
    const b = await enqueue("B");
    await remove(a.id);
    const items = await getAll();
    expect(items.map((i) => i.id)).toEqual([b.id]);
  });
});

describe("clear", () => {
  it("empties the store", async () => {
    await enqueue("A");
    await enqueue("B");
    await clear();
    const items = await getAll();
    expect(items).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 3.4 — SSR guard
// ---------------------------------------------------------------------------
describe("SSR guard", () => {
  it("returns no-ops when window is undefined", async () => {
    // Temporarily hide window.
    const originalWindow = globalThis.window;
    // @ts-expect-error — intentional SSR simulation
    delete globalThis.window;

    try {
      // None of these should throw; default values returned.
      const id = await enqueue("SSR");
      // enqueue returns a QueuedMessage with empty/placeholder values
      expect(id).toBeDefined();

      const items = await getAll();
      expect(items).toEqual([]);

      // These should silently no-op.
      await expect(markInFlight("x")).resolves.toBeUndefined();
      await expect(markPending("x")).resolves.toBeUndefined();
      await expect(remove("x")).resolves.toBeUndefined();
      await expect(clear()).resolves.toBeUndefined();
    } finally {
      // Restore window.
      globalThis.window = originalWindow;
    }
  });
});
