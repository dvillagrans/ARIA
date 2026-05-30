"use client";

/**
 * Chat page — Phase 6 update.
 *
 * Phase 1 behavior preserved:
 * - Fetches conversation history from Supabase on mount.
 * - Appends user message optimistically on submit.
 * - POSTs to /api/chat (Next.js route handler) which injects user_id server-side.
 * - Rolls back optimistic message on API error (online path only).
 *
 * Phase 3 additions:
 * - Message type extended with optional metadata field.
 * - After loadHistory() resolves, checks for today's briefing deduplication.
 * - If no briefing found in history for today, fetches GET /api/briefing.
 * - Injects briefing as first message with stale indicator when stale=true.
 *
 * Phase 6 additions:
 * - Integrates useOfflineQueue hook for offline detection and drain.
 * - When offline, enqueues message to IDB instead of fetching.
 * - Shows offline banner with pending count when !isOnline.
 * - Shows syncing indicator during drain.
 * - Drain callbacks replace queued messages with real responses.
 *
 * Spec §4 — chat/page.tsx UI contract.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import MessageList from "@/components/chat/MessageList";
import MessageInput from "@/components/chat/MessageInput";
import type { Message as BaseMessage } from "@/components/chat/MessageList";
import { useOfflineQueue } from "@/lib/hooks/use-offline-queue";

// Extend base Message with the queued flag used for offline optimistic display.
interface Message extends BaseMessage {
  queued?: boolean;
}

let _messageCounter = 0;
function nextId(): string {
  return `local-${++_messageCounter}-${Date.now()}`;
}

interface BriefingMetadata {
  intent: "briefing";
  date: string;
  cached: boolean;
  stale: boolean;
  generated_at: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const optimisticIdRef = useRef<string | null>(null);

  const { isOnline, isSyncing, pendingCount, enqueueMessage, drainQueue } =
    useOfflineQueue();

  // Wire drain callbacks: replace queued message with real data on success,
  // keep it as-is on failure (no rollback per spec §4).
  const handleMessageSent = useCallback(
    (
      localId: string,
      responseData: { confirmation_text: string }
    ) => {
      setMessages((prev) => {
        // Replace queued user message with a real assistant reply appended.
        const withoutQueued = prev.map((m) =>
          m.id === localId ? { ...m, queued: false } : m
        );
        const assistantMsg: Message = {
          id: nextId(),
          role: "assistant",
          content: responseData.confirmation_text ?? "Done.",
        };
        return [...withoutQueued, assistantMsg];
      });
    },
    []
  );

  const handleMessageFailed = useCallback((_localId: string) => {
    // Keep queued message as-is — no rollback on drain failure.
  }, []);

  // Trigger drain with bound callbacks when the hook fires the online event.
  // We do this by watching isOnline transitions — when it becomes true and
  // pendingCount > 0, drain immediately with the proper callbacks.
  const pendingCountRef = useRef(pendingCount);
  useEffect(() => {
    pendingCountRef.current = pendingCount;
  }, [pendingCount]);

  useEffect(() => {
    if (isOnline && pendingCountRef.current > 0) {
      drainQueue(handleMessageSent, handleMessageFailed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline]);

  // Load conversation history on mount, then inject today's briefing if needed.
  useEffect(() => {
    async function loadHistoryAndBriefing() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) return;

      const { data, error: fetchError } = await supabase
        .from("conversations")
        .select("id, role, content, metadata")
        .eq("user_id", user.id)
        .order("created_at", { ascending: true })
        .limit(20);

      if (fetchError) {
        console.error("[chat] failed to load history:", fetchError);
        return;
      }

      const history: Message[] = data
        ? data.map((row) => ({
            id: row.id,
            role: row.role as "user" | "assistant",
            content: row.content,
            metadata: row.metadata ?? undefined,
          }))
        : [];

      // Deduplicate briefing: skip fetch if today's briefing is already in history.
      const today = new Date().toISOString().split("T")[0];
      const firstMsg = history[0];
      const hasTodayBriefing =
        firstMsg?.role === "assistant" &&
        (firstMsg?.metadata as BriefingMetadata | undefined)?.intent ===
          "briefing" &&
        (firstMsg?.metadata as BriefingMetadata | undefined)?.date === today;

      if (hasTodayBriefing) {
        setMessages(history);
        return;
      }

      // Fetch today's briefing and prepend as first message.
      try {
        const res = await fetch("/api/briefing");
        if (res.ok) {
          const briefingData = await res.json();
          const briefingMsg: Message = {
            id: "briefing-" + today,
            role: "assistant",
            content: briefingData.stale
              ? briefingData.content + "\n\n_(Updated recently — briefing may be slightly stale.)_"
              : briefingData.content,
            metadata: {
              intent: "briefing",
              date: briefingData.date,
              cached: briefingData.cached,
              stale: briefingData.stale,
              generated_at: briefingData.generated_at,
            },
          };
          setMessages([briefingMsg, ...history]);
          return;
        }
      } catch (err) {
        console.error("[chat] briefing fetch error:", err);
      }

      // Briefing fetch failed — show history without briefing.
      setMessages(history);
    }

    loadHistoryAndBriefing();
  }, []);

  async function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    setError(null);
    setIsLoading(true);

    // Optimistic append.
    const optimisticId = nextId();
    optimisticIdRef.current = optimisticId;
    const optimisticMsg: Message = {
      id: optimisticId,
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, optimisticMsg]);

    // Offline path: enqueue and mark as queued. Do NOT roll back.
    if (!isOnline) {
      const localId = await enqueueMessage(trimmed);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === optimisticId
            ? { ...m, id: localId, content: "Queued for sending", queued: true }
            : m
        )
      );
      setIsLoading(false);
      optimisticIdRef.current = null;
      return;
    }

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!res.ok) {
        // Roll back optimistic message on error (online path only).
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        setError("Something went wrong. Please try again.");
        return;
      }

      const data = await res.json();
      const assistantMsg: Message = {
        id: nextId(),
        role: "assistant",
        content: data.confirmation_text ?? "Done.",
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      // Online but fetch failed — existing rollback behavior.
      setMessages((prev) =>
        prev.filter((m) => m.id !== optimisticId)
      );
      setError("Network error. Please check your connection.");
      console.error("[chat] fetch error:", err);
    } finally {
      setIsLoading(false);
      optimisticIdRef.current = null;
    }
  }

  return (
    <main className="flex flex-col h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="shrink-0 flex items-center px-4 py-3 border-b border-gray-700">
        <h1 className="text-lg font-semibold">ARIA</h1>
      </header>

      {/* Offline banner — shown when !isOnline; spec §4 offline banner */}
      {!isOnline && (
        <div
          role="status"
          className="shrink-0 px-4 py-2 bg-yellow-900/60 text-yellow-200 text-sm text-center"
        >
          You are offline. Messages will be sent when you reconnect.
          {pendingCount > 0 && ` (${pendingCount} queued)`}
        </div>
      )}

      {/* Syncing indicator — shown during drain; spec §4 syncing indicator */}
      {isSyncing && (
        <div
          role="status"
          aria-live="polite"
          className="shrink-0 px-4 py-2 bg-blue-900/40 text-blue-200 text-sm text-center"
        >
          Syncing {pendingCount} messages...
        </div>
      )}

      {/* Message list — fills remaining height */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageList messages={messages} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="shrink-0 px-4 py-2 bg-red-900/60 text-red-200 text-sm text-center">
          {error}
        </div>
      )}

      {/* Input pinned to bottom */}
      <div className="shrink-0">
        <MessageInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          disabled={isLoading}
        />
      </div>
    </main>
  );
}
