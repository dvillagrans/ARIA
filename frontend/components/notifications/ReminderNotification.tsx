"use client";

import { AnimatePresence, motion } from "framer-motion";
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
  return (
    <div className="fixed bottom-above-nav md:bottom-4 right-4 left-4 md:left-auto z-50 flex flex-col gap-2 md:max-w-sm md:w-80">
      <AnimatePresence>
        {reminders.map((reminder) => (
          <motion.div
            key={reminder.id}
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }}
            className="bg-bg-surface border border-border-subtle rounded-xl shadow-lg p-4"
          >
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center shrink-0 mt-0.5">
                <Bell className="h-4 w-4 text-accent" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">Reminder</p>
                <p className="text-sm text-text-secondary mt-0.5 line-clamp-2">
                  {reminder.title}
                </p>
                <p className="text-xs text-text-muted mt-1">
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
                className="shrink-0 p-1.5 rounded hover:bg-bg-elevated transition-colors"
                aria-label="Dismiss"
              >
                <X className="h-3.5 w-3.5 text-text-muted" />
              </button>
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => onAcknowledge(reminder.id)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-accent-muted hover:bg-accent/20 text-accent text-sm font-medium rounded-lg transition-colors"
              >
                <Check className="h-3.5 w-3.5" />
                Done
              </button>
              <button
                onClick={() => onDismiss(reminder.id)}
                className="flex-1 px-3 py-2 text-text-muted text-sm hover:text-text-secondary hover:bg-bg-elevated rounded-lg transition-colors"
              >
                Snooze
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
