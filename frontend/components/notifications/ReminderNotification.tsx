"use client";

import { Bell, X, Check } from "lucide-react";
import type { DueReminder } from "@/lib/hooks/use-reminder-poll";

interface ReminderNotificationProps {
  reminders: DueReminder[];
  onAcknowledge: (id: string) => void;
  onDismiss: (id: string) => void;
}

export default function ReminderNotification({
  reminders,
  onAcknowledge,
  onDismiss,
}: ReminderNotificationProps) {
  if (reminders.length === 0) return null;

  return (
    <div className="fixed bottom-20 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {reminders.map((reminder) => (
        <div
          key={reminder.id}
          className="bg-bg-surface border border-accent/30 rounded-xl shadow-lg p-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
        >
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center shrink-0 mt-0.5">
              <Bell className="h-4 w-4 text-accent" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary">
                Reminder
              </p>
              <p className="text-sm text-text-secondary mt-0.5 line-clamp-2">
                {reminder.title}
              </p>
              <p className="text-[10px] text-text-muted mt-1">
                Due{" "}
                {new Date(reminder.due_at).toLocaleTimeString(undefined, {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                {reminder.amount != null &&
                  ` · ${reminder.currency ?? ""} ${reminder.amount}`}
              </p>
            </div>
            <button
              onClick={() => onDismiss(reminder.id)}
              className="shrink-0 p-1 rounded hover:bg-bg-elevated transition-colors"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5 text-text-muted" />
            </button>
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => onAcknowledge(reminder.id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-accent/10 hover:bg-accent/20 text-accent text-xs font-medium rounded-lg transition-colors"
            >
              <Check className="h-3.5 w-3.5" />
              Done
            </button>
            <button
              onClick={() => onDismiss(reminder.id)}
              className="flex-1 px-3 py-1.5 text-text-muted text-xs hover:text-text-secondary hover:bg-bg-elevated rounded-lg transition-colors"
            >
              Snooze
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
