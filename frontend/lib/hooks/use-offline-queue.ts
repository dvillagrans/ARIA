/**
 * use-offline-queue.ts — React hook for offline message queuing and drain.
 *
 * Exposes:
 *   isOnline     — mirrors navigator.onLine, updated via window events
 *   isSyncing    — true while drain is in progress
 *   pendingCount — count of IDB records with status "pending"
 *   enqueueMessage(text) — persists to IDB, increments pendingCount
 *   drainQueue(onSent, onFailed) — sequentially flushes pending items
 *
 * Spec §1 — use-offline-queue hook contract.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  enqueue,
  getAll,
  markInFlight,
  markPending,
  remove,
} from "@/lib/idb/message-queue";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseOfflineQueueResult {
  isOnline: boolean;
  isSyncing: boolean;
  pendingCount: number;
  enqueueMessage: (text: string) => Promise<string>;
  drainQueue: (
    onMessageSent: (
      localId: string,
      responseData: { confirmation_text: string }
    ) => void,
    onMessageFailed: (localId: string) => void
  ) => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOfflineQueue(): UseOfflineQueueResult {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [isSyncing, setIsSyncing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  // Ref to hold stable drainQueue so the online handler can call it without
  // stale closure issues.
  const drainQueueRef = useRef<UseOfflineQueueResult["drainQueue"] | null>(
    null
  );

  // ---------------------------------------------------------------------------
  // drainQueue — sequential flush of pending IDB items
  // ---------------------------------------------------------------------------
  const drainQueue = useCallback<UseOfflineQueueResult["drainQueue"]>(
    async (onMessageSent, onMessageFailed) => {
      const items = await getAll();
      const pending = items.filter((i) => i.status === "pending");
      if (pending.length === 0) return;

      setIsSyncing(true);

      for (const item of pending) {
        await markInFlight(item.id);
        try {
          const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: item.text }),
          });

          if (!res.ok) throw new Error(`HTTP ${res.status}`);

          const data = (await res.json()) as { confirmation_text: string };
          await remove(item.id);
          onMessageSent(item.id, data);
        } catch {
          // Reset this item so it can be retried on next reconnect.
          await markPending(item.id);
          onMessageFailed(item.id);
        }
      }

      // Recount remaining pending items after drain.
      const remaining = await getAll();
      setPendingCount(remaining.filter((i) => i.status === "pending").length);
      setIsSyncing(false);
    },
    []
  );

  // Keep ref in sync with the latest drainQueue callback.
  useEffect(() => {
    drainQueueRef.current = drainQueue;
  }, [drainQueue]);

  // ---------------------------------------------------------------------------
  // Effect 1: sync navigator.onLine + register online/offline listeners
  // ---------------------------------------------------------------------------
  useEffect(() => {
    setIsOnline(navigator.onLine);

    const handleOnline = () => {
      setIsOnline(true);
      // Trigger drain with no-op callbacks — caller-provided callbacks are
      // wired via the drainQueue prop passed to chat/page.tsx.
      // We call via ref to avoid stale closure; chat page binds callbacks.
      drainQueueRef.current?.(() => {}, () => {});
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []); // empty deps — register once

  // ---------------------------------------------------------------------------
  // Effect 2: mount-time IDB read — reset any in-flight → pending (crashed
  // previous session recovery), then set initial pendingCount.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function initFromIDB() {
      const items = await getAll();
      // Reset any in-flight items left by a previous crashed session.
      const inFlight = items.filter((i) => i.status === "in-flight");
      await Promise.all(inFlight.map((i) => markPending(i.id)));
      // Recount after reset.
      const resetItems = await getAll();
      setPendingCount(
        resetItems.filter((i) => i.status === "pending").length
      );
    }

    initFromIDB();
  }, []); // empty deps — run once on mount

  // ---------------------------------------------------------------------------
  // enqueueMessage — add to IDB and increment count
  // ---------------------------------------------------------------------------
  const enqueueMessage = useCallback(async (text: string): Promise<string> => {
    const msg = await enqueue(text);
    setPendingCount((c) => c + 1);
    return msg.id;
  }, []);

  return {
    isOnline,
    isSyncing,
    pendingCount,
    enqueueMessage,
    drainQueue,
  };
}
