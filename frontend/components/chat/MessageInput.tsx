"use client";

/**
 * MessageInput — textarea + send button.
 *
 * Enter sends the message; Shift+Enter inserts a newline.
 * The `disabled` prop locks both the textarea and button during in-flight requests.
 *
 * Spec §6: input disabled during pending request.
 */

import { KeyboardEvent, useRef } from "react";

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export default function MessageInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) {
        onSubmit();
      }
    }
  }

  return (
    <div className="flex items-end gap-2 p-4 border-t border-gray-700 bg-gray-900">
      <textarea
        ref={textareaRef}
        className="flex-1 resize-none rounded-xl bg-gray-800 text-gray-100 placeholder-gray-500 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed max-h-40"
        placeholder="Message ARIA…"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-label="Message input"
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        className="shrink-0 rounded-xl bg-indigo-500 hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-3 text-sm font-medium transition-colors"
        aria-label="Send message"
      >
        Send
      </button>
    </div>
  );
}
