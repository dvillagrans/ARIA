/**
 * message-queue.ts — Offline message queue backed by IndexedDB.
 *
 * SSR-safe: every exported function returns a no-op / empty value when
 * `typeof window === "undefined"`.
 *
 * Spec §1 — offline-message-queue module contract.
 */

import { openDB, type IDBPDatabase } from "idb";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type QueueStatus = "pending" | "in-flight";

export interface QueuedMessage {
  id: string;
  text: string;
  status: QueueStatus;
  queuedAt: number;
}

// ---------------------------------------------------------------------------
// DB constants
// ---------------------------------------------------------------------------

const DB_NAME = "aria-offline-queue";
const STORE_NAME = "messages";
const DB_VERSION = 1;

// ---------------------------------------------------------------------------
// Lazy DB singleton (cached promise, not re-opened on every call)
// ---------------------------------------------------------------------------

let dbPromise: Promise<IDBPDatabase<QueuedMessage>> | null = null;

function getDB(): Promise<IDBPDatabase<QueuedMessage>> | null {
  if (typeof window === "undefined") return null;

  if (!dbPromise) {
    dbPromise = openDB<QueuedMessage>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME as never)) {
          db.createObjectStore(STORE_NAME as never, { keyPath: "id" });
        }
      },
    }) as Promise<IDBPDatabase<QueuedMessage>>;
  }

  return dbPromise;
}

/**
 * Reset the cached DB promise — used in tests to force re-open after
 * fake-indexeddb replaces the global indexedDB between test suites.
 * Do NOT call this in production code.
 */
export function _resetDBForTesting(): void {
  dbPromise = null;
}

// ---------------------------------------------------------------------------
// Exported functions
// ---------------------------------------------------------------------------

/**
 * Enqueue a new message with status "pending".
 * Returns the full QueuedMessage record written to IDB.
 * SSR: returns a placeholder QueuedMessage without IDB access.
 */
export async function enqueue(text: string): Promise<QueuedMessage> {
  const id = crypto.randomUUID();
  const record: QueuedMessage = {
    id,
    text,
    status: "pending",
    queuedAt: Date.now(),
  };

  const db = getDB();
  if (!db) return record; // SSR no-op

  const resolved = await db;
  await resolved.put(STORE_NAME as never, record as never);
  return record;
}

/**
 * Return all queued messages ordered by queuedAt ascending.
 * SSR: returns [].
 */
export async function getAll(): Promise<QueuedMessage[]> {
  const db = getDB();
  if (!db) return [];

  const resolved = await db;
  const tx = resolved.transaction(STORE_NAME as never, "readonly");
  const store = tx.objectStore(STORE_NAME as never);
  // getAll returns records in key insertion order (keyPath: 'id' is UUID).
  // We need queuedAt ordering — use index or sort after fetch.
  const all = (await store.getAll()) as QueuedMessage[];
  return all.sort((a, b) => a.queuedAt - b.queuedAt);
}

/**
 * Update the status of a single record.
 * SSR: no-op.
 */
export async function updateStatus(
  id: string,
  status: QueueStatus
): Promise<void> {
  const db = getDB();
  if (!db) return;

  const resolved = await db;
  const tx = resolved.transaction(STORE_NAME as never, "readwrite");
  const store = tx.objectStore(STORE_NAME as never);
  const record = (await store.get(id)) as QueuedMessage | undefined;
  if (record) {
    await store.put({ ...record, status } as never);
  }
  await tx.done;
}

/**
 * Mark a record as "in-flight" — called before starting a fetch.
 * SSR: no-op.
 */
export async function markInFlight(id: string): Promise<void> {
  return updateStatus(id, "in-flight");
}

/**
 * Reset a record to "pending" — called on drain failure.
 * SSR: no-op.
 */
export async function markPending(id: string): Promise<void> {
  return updateStatus(id, "pending");
}

/**
 * Remove a single record by id.
 * SSR: no-op.
 */
export async function remove(id: string): Promise<void> {
  const db = getDB();
  if (!db) return;

  const resolved = await db;
  await resolved.delete(STORE_NAME as never, id as never);
}

/**
 * Remove all records from the store.
 * SSR: no-op.
 */
export async function clear(): Promise<void> {
  const db = getDB();
  if (!db) return;

  const resolved = await db;
  await resolved.clear(STORE_NAME as never);
}
