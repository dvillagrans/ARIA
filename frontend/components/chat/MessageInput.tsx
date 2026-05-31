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
    <div className="border-t border-bg-elevated bg-bg-surface/90 backdrop-blur-sm px-3 py-2.5 md:px-4 md:py-3">
      <div className="flex items-end gap-2 bg-bg-elevated rounded-2xl border border-bg-hover focus-within:border-accent/40 focus-within:shadow-[0_0_0_2px_var(--color-accent-muted)] transition-all px-3 py-1.5">
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
          whileHover={{ scale: 1.05 }}
          className="shrink-0 rounded-full bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed text-white p-2 transition-colors"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </motion.button>
      </div>
    </div>
  );
}
