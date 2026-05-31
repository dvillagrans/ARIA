"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Bell, Pencil, Trash2, Check, X, CalendarSync, Calendar } from "lucide-react";
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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDueAt, setEditDueAt] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

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

  // Polling fallback — fetch fresh reminders every 10s in case Realtime is delayed
  useEffect(() => {
    const supabase = createClient();
    const interval = setInterval(async () => {
      const { data } = await supabase
        .from("reminders")
        .select("id, title, due_at, is_done, amount, currency, calendar_event_id")
        .eq("user_id", userId)
        .eq("is_done", false)
        .order("due_at", { ascending: true })
        .limit(20);
      if (data) {
        setReminders((prev) => {
          const ids = new Set(data.map((r) => r.id));
          // Merge: keep local items not in DB (optimistic), add new from DB
          const merged = [
            ...prev.filter((r) => !ids.has(r.id)),
            ...data,
          ].filter((r) => !r.is_done);
          return merged.sort(
            (a, b) =>
              new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
          );
        });
      }
    }, 10_000);
    return () => clearInterval(interval);
  }, [userId]);

  function startEdit(reminder: Reminder) {
    setEditingId(reminder.id);
    setEditTitle(reminder.title);
    // Format for datetime-local input
    const d = new Date(reminder.due_at);
    const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    setEditDueAt(local);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditTitle("");
    setEditDueAt("");
  }

  async function saveEdit(id: string) {
    const dueAtIso = editDueAt ? new Date(editDueAt).toISOString() : undefined;
    try {
      const res = await fetch(`/api/reminders/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editTitle,
          ...(dueAtIso && { due_at: dueAtIso }),
        }),
      });
      if (res.ok) {
        setReminders((prev) =>
          prev.map((r) =>
            r.id === id
              ? { ...r, title: editTitle, ...(dueAtIso && { due_at: dueAtIso }) }
              : r
          )
        );
      }
    } catch {
      // Silent
    }
    cancelEdit();
  }

  async function deleteReminder(id: string) {
    try {
      await fetch(`/api/reminders/${id}`, { method: "DELETE" });
    } catch {
      // Silent
    }
    setReminders((prev) => prev.filter((r) => r.id !== id));
  }

  async function syncAll() {
    setIsSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch("/api/reminders/sync-all", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSyncResult(`Synced ${data.synced}/${data.total}`);
      } else {
        setSyncResult("Sync failed");
      }
    } catch {
      setSyncResult("Sync failed");
    }
    setIsSyncing(false);
    setTimeout(() => setSyncResult(null), 3000);
  }

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
    <div className="px-2">
      <div className="flex items-center justify-between px-2.5 py-1 mb-1">
        <span className="text-[10px] text-text-muted uppercase tracking-wider">Reminders</span>
        <button
          onClick={syncAll}
          disabled={isSyncing}
          className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-text-muted hover:text-accent rounded transition-colors disabled:opacity-50"
          title="Sync all to Google Calendar"
        >
          <CalendarSync className={`h-3 w-3 ${isSyncing ? "animate-spin" : ""}`} />
          {syncResult && <span className="text-accent">{syncResult}</span>}
        </button>
      </div>
      <ul className="space-y-0.5">
      {reminders.map((reminder) => {
        const isEditing = editingId === reminder.id;

        return (
          <li
            key={reminder.id}
            className="px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors group"
          >
            {isEditing ? (
              <div className="flex flex-col gap-1.5">
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full bg-bg-root border border-bg-hover rounded px-2 py-1 text-sm text-text-primary outline-none focus:border-accent"
                  autoFocus
                />
                <input
                  type="datetime-local"
                  value={editDueAt}
                  onChange={(e) => setEditDueAt(e.target.value)}
                  className="w-full bg-bg-root border border-bg-hover rounded px-2 py-1 text-xs text-text-secondary outline-none focus:border-accent"
                />
                <div className="flex gap-1.5">
                  <button
                    onClick={() => saveEdit(reminder.id)}
                    className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-accent/10 hover:bg-accent/20 text-accent text-xs rounded transition-colors"
                  >
                    <Check className="h-3 w-3" />
                    Save
                  </button>
                  <button
                    onClick={cancelEdit}
                    className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-text-muted hover:text-text-secondary text-xs rounded hover:bg-bg-hover transition-colors"
                  >
                    <X className="h-3 w-3" />
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-1.5">
                  <p className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors flex-1">
                    {reminder.title}
                  </p>
                  {reminder.calendar_event_id && (
                    <Calendar className="h-3 w-3 text-accent shrink-0" title="Synced to Google Calendar" />
                  )}
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <p className="text-[10px] text-text-muted">
                    {new Date(reminder.due_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    {reminder.amount != null &&
                      ` · ${reminder.currency ?? ""} ${reminder.amount}`}
                  </p>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => startEdit(reminder)}
                      className="p-0.5 rounded hover:bg-bg-hover text-text-muted hover:text-text-secondary transition-colors"
                      aria-label="Edit reminder"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      onClick={() => deleteReminder(reminder.id)}
                      className="p-0.5 rounded hover:bg-red-900/30 text-text-muted hover:text-red-400 transition-colors"
                      aria-label="Delete reminder"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </li>
        );
      })}
    </ul>
    </div>
  );
}
