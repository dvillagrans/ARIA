"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { WifiOff, Loader2, X } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import MessageList from "@/components/chat/MessageList";
import MessageInput from "@/components/chat/MessageInput";
import ReminderNotification from "@/components/notifications/ReminderNotification";
import type { Message as DisplayMessage } from "@/components/chat/MessageList";
import { useOfflineQueue } from "@/lib/hooks/use-offline-queue";
import { useReminderPoll } from "@/lib/hooks/use-reminder-poll";

export interface ChatViewProps {
  projectId?: string;
  projectName?: string;
  projectColor?: string;
  /** Hide the built-in header when an outer layout already renders one. */
  hideHeader?: boolean;
}

let _localCounter = 0;
function localId() {
  return `local-${++_localCounter}-${Date.now()}`;
}

export default function ChatView({ projectId, projectName, projectColor, hideHeader }: ChatViewProps) {
  const isProjectChat = !!projectId;

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [briefing, setBriefing] = useState<DisplayMessage | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const { isOnline, isSyncing, pendingCount, enqueueMessage, drainQueue } =
    useOfflineQueue();
  const { dueReminders, acknowledge, dismiss } = useReminderPoll();

  // ── History + briefing ────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function load() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) { setHistoryLoaded(true); return; }

      let query = supabase
        .from("conversations")
        .select("id, role, content, metadata, created_at")
        .eq("user_id", user.id)
        .order("created_at", { ascending: true })
        .limit(20);

      query = isProjectChat
        ? query.eq("project_id", projectId)
        : query.is("project_id", null);

      const { data, error } = await query;
      if (cancelled) return;

      if (!error && data) {
        setMessages(
          data.map((r) => ({
            id: r.id,
            role: r.role as "user" | "assistant",
            content: r.content,
            created_at: r.created_at,
          }))
        );

        if (!isProjectChat) {
          const today = new Date().toISOString().split("T")[0];
          const first = data[0];
          const hasBriefing =
            first?.role === "assistant" &&
            first?.metadata?.intent === "briefing" &&
            first?.metadata?.date === today;

          if (!hasBriefing) {
            try {
              const res = await fetch("/api/briefing");
              if (res.ok && !cancelled) {
                const bd = await res.json();
                setBriefing({
                  id: `briefing-${today}`,
                  role: "assistant",
                  content: bd.stale
                    ? `${bd.content}\n\n_(Updated recently — briefing may be slightly stale.)_`
                    : bd.content,
                });
              }
            } catch { /* non-fatal */ }
          }
        }
      }

      if (!cancelled) setHistoryLoaded(true);
    }

    load();
    return () => { cancelled = true; };
  }, [isProjectChat, projectId]);

  // ── Offline queue drain ───────────────────────────────────────────────
  const handleQueued = useCallback(
    (_id: string, data: { confirmation_text: string }) => {
      setMessages((prev) => [
        ...prev,
        { id: localId(), role: "assistant" as const, content: data.confirmation_text ?? "Done." },
      ]);
    },
    []
  );

  const pendingRef = useRef(pendingCount);
  useEffect(() => { pendingRef.current = pendingCount; }, [pendingCount]);
  useEffect(() => {
    if (isOnline && pendingRef.current > 0 && !isProjectChat) {
      drainQueue(handleQueued, () => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline]);

  // ── Submit with streaming ─────────────────────────────────────────────
  async function onSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    setChatError(null);

    if (!isOnline && !isProjectChat) {
      const qid = await enqueueMessage(trimmed);
      setMessages((prev) => [
        ...prev,
        { id: qid, role: "user" as const, content: "Queued for sending" },
      ]);
      return;
    }

    const optimisticId = localId();
    const now = new Date().toISOString();
    setMessages((prev) => [...prev, { id: optimisticId, role: "user", content: trimmed, created_at: now }]);
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: trimmed }],
          ...(isProjectChat && { project_id: projectId }),
        }),
      });

      if (!res.ok || !res.body) {
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
        setChatError("Something went wrong. Please try again.");
        return;
      }

      // Stream the response word-by-word into the assistant message.
      const assistantId = localId();
      setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", created_at: new Date().toISOString() }]);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + chunk } : m
          )
        );
      }
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      setChatError("Network error. Please check your connection.");
      console.error("[chat] fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────
  const displayMessages: DisplayMessage[] = [
    ...(briefing ? [briefing] : []),
    ...messages,
  ];

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-bg-root text-text-primary">
      {/* Header */}
      {!hideHeader && (
        <header className="shrink-0 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm pt-safe">
          <div className="flex items-center gap-2 px-4 py-2.5">
          {isProjectChat ? (
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${projectColor}25` }}
            >
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: projectColor }} />
            </div>
          ) : (
            <img src="/logo.svg" alt="ARIA" className="w-7 h-7 rounded-lg shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-semibold truncate">
              {isProjectChat ? projectName : "ARIA"}
            </h1>
            {isProjectChat ? (
              <p className="text-[11px] text-text-muted">Project chat</p>
            ) : (
              !isOnline && (
                <p className="text-[11px]" style={{ color: "var(--color-status-warning-fg)" }}>Offline</p>
              )
            )}
          </div>
          </div>
        </header>
      )}

      {/* Offline banner */}
      {!isOnline && !isProjectChat && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          role="status"
          className="banner banner-warning"
        >
          <WifiOff className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">
            Offline{pendingCount > 0 && ` — ${pendingCount} queued`}
          </span>
        </motion.div>
      )}

      {/* Syncing banner */}
      {isSyncing && !isProjectChat && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          role="status"
          aria-live="polite"
          className="banner banner-info"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
          <span>Syncing {pendingCount} messages…</span>
        </motion.div>
      )}

      {/* Messages */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageList
          messages={displayMessages}
          isLoading={!historyLoaded || (isLoading && messages.length > 0)}
        />
      </div>

      {/* Error banner */}
      {chatError && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="banner banner-error border-t"
        >
          <span className="flex-1">{chatError}</span>
          <button
            onClick={() => setChatError(null)}
            className="shrink-0 p-1.5 rounded hover:bg-status-error-bg transition-colors"
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
          onSubmit={onSubmit}
          disabled={isLoading}
        />
      </div>

      {/* Reminders — general chat only */}
      {!isProjectChat && (
        <ReminderNotification
          reminders={dueReminders}
          onAcknowledge={acknowledge}
          onDismiss={dismiss}
        />
      )}
    </main>
  );
}
