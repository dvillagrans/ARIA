"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface DueReminder {
  id: string;
  title: string;
  due_at: string;
  amount?: number;
  currency?: string;
  project_id?: string;
}

const POLL_INTERVAL_MS = 60_000; // 60 seconds

export function useReminderPoll() {
  const [dueReminders, setDueReminders] = useState<DueReminder[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const shownIdsRef = useRef<Set<string>>(new Set());

  const fetchDue = useCallback(async () => {
    try {
      const res = await fetch("/api/reminders/due");
      if (!res.ok) return;
      const data: DueReminder[] = await res.json();

      // Only show reminders we haven't already shown in this session
      const newReminders = data.filter((r) => !shownIdsRef.current.has(r.id));
      if (newReminders.length > 0) {
        newReminders.forEach((r) => shownIdsRef.current.add(r.id));
        setDueReminders((prev) => [...prev, ...newReminders]);
      }
    } catch {
      // Silent — polling errors shouldn't disrupt the user
    }
  }, []);

  const acknowledge = useCallback(async (reminderId: string) => {
    try {
      await fetch("/api/reminders/acknowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reminder_id: reminderId }),
      });
    } catch {
      // Silent
    }
    setDueReminders((prev) => prev.filter((r) => r.id !== reminderId));
  }, []);

  const dismiss = useCallback((reminderId: string) => {
    setDueReminders((prev) => prev.filter((r) => r.id !== reminderId));
  }, []);

  useEffect(() => {
    setIsPolling(true);
    fetchDue(); // Initial check
    intervalRef.current = setInterval(fetchDue, POLL_INTERVAL_MS);

    return () => {
      setIsPolling(false);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchDue]);

  return { dueReminders, acknowledge, dismiss, isPolling };
}
