"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Bot, WifiOff, Loader2, ChevronLeft, X } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import MessageList from "@/components/chat/MessageList";
import MessageInput from "@/components/chat/MessageInput";
import ReminderNotification from "@/components/notifications/ReminderNotification";
import type { Message as BaseMessage } from "@/components/chat/MessageList";
import { useOfflineQueue } from "@/lib/hooks/use-offline-queue";
import { useReminderPoll } from "@/lib/hooks/use-reminder-poll";

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
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optimisticIdRef = useRef<string | null>(null);

  const { isOnline, isSyncing, pendingCount, enqueueMessage, drainQueue } =
    useOfflineQueue();

  const { dueReminders, acknowledge, dismiss } = useReminderPoll();

  const handleMessageSent = useCallback(
    (localId: string, responseData: { confirmation_text: string }) => {
      setMessages((prev) => {
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

  const handleMessageFailed = useCallback((_localId: string) => {}, []);

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
        setIsHistoryLoading(false);
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

      const today = new Date().toISOString().split("T")[0];
      const firstMsg = history[0];
      const hasTodayBriefing =
        firstMsg?.role === "assistant" &&
        (firstMsg?.metadata as BriefingMetadata | undefined)?.intent === "briefing" &&
        (firstMsg?.metadata as BriefingMetadata | undefined)?.date === today;

      if (hasTodayBriefing) {
        setMessages(history);
        setIsHistoryLoading(false);
        return;
      }

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
          setIsHistoryLoading(false);
          return;
        }
      } catch (err) {
        console.error("[chat] briefing fetch error:", err);
      }

      setMessages(history);
      setIsHistoryLoading(false);
    }

    loadHistoryAndBriefing();
  }, []);

  async function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    setError(null);
    setIsLoading(true);

    const optimisticId = nextId();
    optimisticIdRef.current = optimisticId;
    const optimisticMsg: Message = {
      id: optimisticId,
      role: "user",
      content: trimmed,
    };
    setMessages((prev) => [...prev, optimisticMsg]);

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
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        setError("Something went wrong. Please try again.");
        setIsLoading(false);
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
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      setError("Network error. Please check your connection.");
      console.error("[chat] fetch error:", err);
    } finally {
      setIsLoading(false);
      optimisticIdRef.current = null;
    }
  }

  return (
    <main className="flex flex-col h-full bg-bg-root text-text-primary">
      {/* Header */}
      <header className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm">
        <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center shrink-0">
          <Bot className="h-4 w-4 text-accent" strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold">ARIA</h1>
          <div className="flex items-center gap-1.5">
            <span className="block w-1.5 h-1.5 rounded-full bg-success animate-pulse-dot" />
            <span className="text-[10px] text-text-muted">Online</span>
          </div>
        </div>
      </header>

      {/* Offline banner */}
      {!isOnline && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          role="status"
          className="shrink-0 flex items-center gap-2 px-4 py-2 bg-amber-950/60 border-b border-amber-900/30 text-amber-200 text-xs"
        >
          <WifiOff className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">
            Offline{pendingCount > 0 && ` — ${pendingCount} queued`}
          </span>
        </motion.div>
      )}

      {/* Syncing banner */}
      {isSyncing && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          role="status"
          aria-live="polite"
          className="shrink-0 flex items-center gap-2 px-4 py-2 bg-blue-950/40 border-b border-blue-900/30 text-blue-200 text-xs"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
          <span>Syncing {pendingCount} messages…</span>
        </motion.div>
      )}

      {/* Message list */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageList messages={messages} isLoading={isHistoryLoading || (isLoading && messages.length > 0)} />
      </div>

      {/* Error banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="shrink-0 flex items-center gap-2 px-4 py-2 bg-red-950/60 border-t border-red-900/30 text-red-200 text-xs"
        >
          <span className="flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="shrink-0 p-0.5 rounded hover:bg-red-900/40 transition-colors"
            aria-label="Dismiss error"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </motion.div>
      )}

      {/* Input */}
      <div className="shrink-0">
        <MessageInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          disabled={isLoading}
        />
      </div>

      {/* Reminder notifications */}
      <ReminderNotification
        reminders={dueReminders}
        onAcknowledge={acknowledge}
        onDismiss={dismiss}
      />
    </main>
  );
}
