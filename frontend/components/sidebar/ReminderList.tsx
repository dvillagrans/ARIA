"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import { useRealtime } from "@/lib/hooks/use-realtime";
import EmptyState from "@/components/ui/EmptyState";

export interface Reminder {
  id: string;
  title: string;
  due_at: string;
  is_done: boolean;
  amount?: number;
  currency?: string;
  [key: string]: unknown;
}

interface ReminderListProps {
  userId: string;
  initialReminders?: Reminder[];
}

export default function ReminderList({ userId, initialReminders = [] }: ReminderListProps) {
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
      <EmptyState
        icon={Bell}
        title="No pending reminders"
        description="Reminders you create will show up here."
      />
    );
  }

  return (
    <ul className="space-y-0.5 px-2">
      {reminders.map((reminder) => (
        <li
          key={reminder.id}
          className="px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors group"
        >
          <p className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors">
            {reminder.title}
          </p>
          <p className="text-[10px] text-text-muted mt-0.5">
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
