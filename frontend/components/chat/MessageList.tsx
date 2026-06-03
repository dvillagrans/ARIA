"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonText } from "@/components/ui/Skeleton";
import MarkdownMessage from "@/components/chat/MarkdownMessage";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
}

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

const messageAnimation = {
  initial: { opacity: 0, y: 12, scale: 0.97 },
  animate: { opacity: 1, y: 0, scale: 1 },
  transition: { type: "spring" as const, stiffness: 400, damping: 30 },
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          icon={MessageSquare}
          title="No messages yet"
          description="Type a message below to begin."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-4 py-6 md:px-8 scrollbar-thin">
      {/* Initial loading skeleton — outside AnimatePresence to avoid key collision */}
      {isLoading && messages.length === 0 && (
        <div className="flex flex-1 flex-col gap-3">
          <div className="flex justify-start">
            <SkeletonText lines={2} className="max-w-[70%]" />
          </div>
          <div className="flex justify-end">
            <SkeletonText lines={1} className="max-w-[50%]" />
          </div>
          <div className="flex justify-start">
            <SkeletonText lines={3} className="max-w-[80%]" />
          </div>
        </div>
      )}

      <AnimatePresence initial={false}>
        {messages.map((msg, i) => {
          const isUser = msg.role === "user";
          const isFirstInTurn = i === 0 || messages[i - 1]?.role !== msg.role;
          const isStreaming = isLoading && i === messages.length - 1 && msg.role === "assistant";
          const showTime = isFirstInTurn;

          return (
            <motion.div
              key={msg.id}
              layout
              {...messageAnimation}
              className={`flex flex-col ${isUser ? "items-end" : "items-start"} mb-4`}
            >
              {/* ARIA › label — only for first assistant message in a sequence */}
              {!isUser && isFirstInTurn && (
                <span className="text-[11px] text-accent mb-1 select-none">ARIA ›</span>
              )}

              {isUser ? (
                /* User: code-block style */
                <div
                  className="max-w-[85%] sm:max-w-[80%] md:max-w-[70%]"
                  style={{
                    background: "#18181b",
                    borderLeft: "2px solid #10b981",
                    borderRadius: "2px",
                    padding: "12px 16px",
                  }}
                >
                  <p className="text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap break-words">
                    {msg.content}
                  </p>
                </div>
              ) : (
                /* Assistant: rendered markdown */
                <div className="max-w-[90%] md:max-w-[80%]">
                  <MarkdownMessage
                    content={msg.content}
                    isStreaming={isStreaming}
                  />
                </div>
              )}

              {showTime && (
                <p className={`text-[11px] text-text-muted mt-1 ${isUser ? "text-right" : "text-left"}`}>
                  {formatTime(msg.created_at ? new Date(msg.created_at) : new Date())}
                </p>
              )}
            </motion.div>
          );
        })}

        {/* Loading dots indicator — shown when waiting for assistant response */}
        {isLoading && messages.length > 0 && messages[messages.length - 1].role !== "assistant" && (
          <motion.div
            key="loading-dots"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start mb-4"
          >
            <span className="text-[11px] text-accent mr-2">ARIA ›</span>
            <div className="loading-dots">
              <span /><span /><span />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={bottomRef} />
    </div>
  );
}
