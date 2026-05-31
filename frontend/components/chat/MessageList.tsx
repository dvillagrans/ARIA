"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonText } from "@/components/ui/Skeleton";

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
    <div className="flex flex-1 flex-col overflow-y-auto p-4 md:px-6 scrollbar-thin">
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
          const showTime = i === 0 || messages[i - 1]?.role !== msg.role || i === messages.length - 1;

          return (
            <motion.div
              key={msg.id}
              layout
              {...messageAnimation}
              className={`flex ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div className={`max-w-[85%] sm:max-w-[80%] md:max-w-[70%] ${isUser ? "order-1" : ""}`}>
                <div
                  className={`relative rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    isUser
                      ? "bg-accent text-white rounded-2xl"
                      : "bg-bg-surface border border-border-subtle text-text-primary rounded-2xl"
                  }`}
                >
                  {msg.content}
                </div>
                {showTime && (
                  <p className={`text-xs px-1 text-text-muted mt-1 ${isUser ? "text-right" : "text-left"}`}>
                    {formatTime(msg.created_at ? new Date(msg.created_at) : new Date())}
                  </p>
                )}
              </div>
            </motion.div>
          );
        })}

        {/* Typing / loading indicator */}
        {isLoading && messages.length > 0 && (
          <motion.div
            key="typing-indicator"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="bg-bg-surface border border-border-subtle rounded-2xl px-4 py-3 flex items-center gap-1.5">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={bottomRef} />
    </div>
  );
}
