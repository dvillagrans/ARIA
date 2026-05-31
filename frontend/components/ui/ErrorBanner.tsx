"use client";

import { X, AlertCircle } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="shrink-0 flex items-center gap-2 px-4 py-2.5 bg-red-950/60 border-b border-red-900/30 text-red-200 text-sm"
    >
      <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="shrink-0 rounded-md p-0.5 hover:bg-red-900/40 transition-colors"
          aria-label="Dismiss error"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
