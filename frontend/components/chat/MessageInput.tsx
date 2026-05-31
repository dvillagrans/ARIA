"use client";

import { KeyboardEvent, useRef, useCallback } from "react";

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
    <div
      className="border-t border-bg-elevated bg-bg-root px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:px-6 md:pt-4 md:pb-4"
    >
      <div
        className="flex items-end gap-3"
        style={{
          border: "1px solid #27272a",
          borderRadius: "2px",
          background: "#09090b",
          padding: "10px 12px",
        }}
      >
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-transparent text-[13px] text-text-primary placeholder-text-muted py-0.5 focus:outline-none max-h-32 leading-relaxed"
          style={{ fontFamily: "inherit" }}
          placeholder="Message ARIA..."
          rows={1}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          aria-label="Message input"
          onFocus={(e) => {
            (e.currentTarget.parentElement as HTMLDivElement).style.borderColor = "#10b981";
          }}
          onBlur={(e) => {
            (e.currentTarget.parentElement as HTMLDivElement).style.borderColor = "#27272a";
          }}
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          className={`shrink-0 text-[18px] leading-none pb-0.5 transition-colors duration-100 disabled:cursor-not-allowed ${
            value.trim() ? "text-accent" : "text-text-muted"
          }`}
          aria-label="Send message"
          style={{ fontFamily: "inherit" }}
        >
          ↵
        </button>
      </div>
    </div>
  );
}
