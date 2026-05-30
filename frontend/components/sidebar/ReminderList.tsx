"use client";

/**
 * ReminderList — pending reminders with Realtime updates.
 *
 * Subscribes to a per-user reminders channel. Updates list on INSERT/UPDATE/DELETE.
 *
 * Spec §7: per-user Realtime channel for reminders.
 * ADR-06.
 */

import { useState } from "react";
import { useRealtime } from "@/lib/hooks/use-realtime";

export interface Reminder {
  id: string;
  title: string;
  due_at: string;
  is_done: boolean;
  amount?: number;
  currency?: string;
}

interface ReminderListProps {
  userId: string;
  initialReminders?: Reminder[];
}

export default function ReminderList({
  userId,
  initialReminders = [],
}: ReminderListProps) {
  const [reminders, setReminders] = useState<Reminder[]>(
    initialReminders.filter((r) => !r.is_done)
  );

  useRealtime<Reminder>(
    [{ table: "reminders", filter: `user_id=eq.${userId}` }],
    (_table, eventType, row) => {
      setReminders((prev) => {
        if (eventType === "INSERT") {
          if (row.is_done) return prev;
          return [...prev, row].sort(
            (a, b) =>
              new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
          );
        }
        if (eventType === "UPDATE") {
          // Remove if marked done, otherwise update in place.
          if (row.is_done) return prev.filter((r) => r.id !== row.id);
          return prev.map((r) => (r.id === row.id ? row : r));
        }
        if (eventType === "DELETE") {
          return prev.filter((r) => r.id !== row.id);
        }
        return prev;
      });
    }
  );

  if (reminders.length === 0) {
    return (
      <p className="text-xs text-gray-500 px-3 py-2">No pending reminders.</p>
    );
  }

  return (
    <ul className="space-y-1">
      {reminders.map((reminder) => (
        <li
          key={reminder.id}
          className="px-3 py-2 rounded-lg hover:bg-gray-800 transition-colors"
        >
          <p className="text-sm text-gray-200 truncate">{reminder.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {new Date(reminder.due_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
            {reminder.amount != null &&
              ` · ${reminder.currency ?? ""} ${reminder.amount}`}
          </p>
        </li>
      ))}
    </ul>
  );
}
