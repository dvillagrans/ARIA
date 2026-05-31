"use client";

import { KeyboardEvent, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export default function MessageInput({
  value = "",
  onChange,
  onSubmit,
  disabled = false,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 128) + "px";
  }, []);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) {
        onSubmit();
      }
    }
  }

  function handleChange(newValue: string) {
    onChange(newValue);
    requestAnimationFrame(autoResize);
  }

  return (
    <div className="border-t border-bg-elevated bg-bg-surface/90 backdrop-blur-sm px-3 pt-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))] md:px-4 md:pt-3 md:pb-3">
      <div className="flex items-end gap-2 bg-bg-elevated rounded-2xl border border-border-subtle focus-within:border-accent transition-all px-3 py-1.5">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-transparent text-text-primary placeholder-text-muted text-sm py-1.5 focus:outline-none max-h-32"
          placeholder="Message ARIA…"
          rows={1}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          aria-label="Message input"
        />
        <motion.button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          whileTap={{ scale: 0.92 }}
          className="shrink-0 rounded-full bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed text-white w-9 h-9 flex items-center justify-center transition-colors"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </motion.button>
      </div>
    </div>
  );
}
