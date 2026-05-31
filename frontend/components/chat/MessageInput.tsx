"use client";

import { KeyboardEvent, useRef, useCallback } from "react";
import { Paperclip, Loader2 } from "lucide-react";

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  onFileAttach?: (file: File) => void;
  isUploading?: boolean;
}

export default function MessageInput({
  value = "",
  onChange,
  onSubmit,
  disabled = false,
  onFileAttach,
  isUploading = false,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && onFileAttach) {
      onFileAttach(file);
    }
    // Reset so the same file can be re-selected if needed
    e.target.value = "";
  }

  return (
    <div className="border-t border-bg-elevated bg-bg-root px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:px-6 md:pt-4 md:pb-4">
      <div
        className="flex items-end gap-3"
        style={{
          border: "1px solid #27272a",
          borderRadius: "2px",
          background: "#09090b",
          padding: "10px 12px",
        }}
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf"
          className="hidden"
          onChange={handleFileChange}
          tabIndex={-1}
          aria-hidden
        />

        {/* Paperclip — only shown when onFileAttach is provided */}
        {onFileAttach && (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isUploading}
            className="shrink-0 text-text-muted hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed pb-0.5"
            aria-label="Attach file"
          >
            {isUploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Paperclip className="h-4 w-4" />
            )}
          </button>
        )}

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
