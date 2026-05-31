"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { AnimatePresence, motion } from "framer-motion";
import {
  CalendarDays,
  CalendarSync,
  Clock,
  Users,
  GraduationCap,
  Stethoscope,
  Calendar,
  Pencil,
  Trash2,
  X,
  Check,
  Loader2,
} from "lucide-react";
import { useRealtime } from "@/lib/hooks/use-realtime";
import EmptyState from "@/components/ui/EmptyState";

export interface CalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  duration_min: number;
  type: string;
  source?: string;
  [key: string]: unknown;
}

interface EventListProps {
  userId: string;
  initialEvents?: CalendarEvent[];
}

interface DayGroup {
  label: string;
  date: string;
  events: CalendarEvent[];
}

const EVENT_TYPES = ["meeting", "class", "appointment", "other"] as const;

function groupByDay(events: CalendarEvent[]): DayGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const nextWeek = new Date(today);
  nextWeek.setDate(nextWeek.getDate() + 7);

  const groups: Map<string, DayGroup> = new Map();

  for (const event of events) {
    const eventDate = new Date(event.starts_at);
    const eventDay = new Date(
      eventDate.getFullYear(),
      eventDate.getMonth(),
      eventDate.getDate()
    );
    const key = eventDay.toISOString().split("T")[0];

    let label: string;
    if (eventDay.getTime() === today.getTime()) {
      label = "Today";
    } else if (eventDay.getTime() === tomorrow.getTime()) {
      label = "Tomorrow";
    } else if (eventDay < nextWeek) {
      label = eventDate.toLocaleDateString(undefined, { weekday: "long" });
    } else {
      label = eventDate.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    }

    if (!groups.has(key)) {
      groups.set(key, { label, date: key, events: [] });
    }
    groups.get(key)!.events.push(event);
  }

  return Array.from(groups.values());
}

function getEventIcon(type: string) {
  switch (type) {
    case "meeting": return <Users className="h-3.5 w-3.5" />;
    case "class": return <GraduationCap className="h-3.5 w-3.5" />;
    case "appointment": return <Stethoscope className="h-3.5 w-3.5" />;
    default: return <Calendar className="h-3.5 w-3.5" />;
  }
}

function getEventColor(type: string): string {
  switch (type) {
    case "meeting": return "bg-blue-500/15 text-blue-400 border-blue-500/20";
    case "class": return "bg-purple-500/15 text-purple-400 border-purple-500/20";
    case "appointment": return "bg-rose-500/15 text-rose-400 border-rose-500/20";
    default: return "bg-accent/15 text-accent border-accent/20";
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatDuration(min: number): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function toLocalDatetimeInput(iso: string): string {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

export default function EventList({ userId, initialEvents = [] }: EventListProps) {
  const [events, setEvents] = useState<CalendarEvent[]>(initialEvents);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());

  // Detail / edit sheet
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [mode, setMode] = useState<"detail" | "edit">("detail");
  const [editTitle, setEditTitle] = useState("");
  const [editType, setEditType] = useState("");
  const [editStartsAt, setEditStartsAt] = useState("");
  const [editDuration, setEditDuration] = useState(0);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useRealtime<CalendarEvent>(
    [{ table: "events", filter: `user_id=eq.${userId}` }],
    (_table, eventType, row) => {
      setEvents((prev) => {
        if (eventType === "INSERT") {
          return [...prev, row].sort(
            (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
          );
        }
        if (eventType === "UPDATE") {
          return prev.map((e) => (e.id === row.id ? row : e));
        }
        if (eventType === "DELETE") {
          return prev.filter((e) => e.id !== row.id);
        }
        return prev;
      });
    }
  );

  useEffect(() => {
    const supabase = createClient();
    const interval = setInterval(async () => {
      const today = new Date().toISOString();
      const { data } = await supabase
        .from("events")
        .select("id, title, starts_at, duration_min, type, source")
        .eq("user_id", userId)
        .gte("starts_at", today)
        .order("starts_at", { ascending: true })
        .limit(50);
      if (data) setEvents(data);
    }, 30_000);
    return () => clearInterval(interval);
  }, [userId]);

  async function syncFromGoogle() {
    setIsSyncing(true);
    setSyncResult(null);
    try {
      const res = await fetch("/api/events/sync", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSyncResult(`+${data.imported} new`);
        const supabase = createClient();
        const today = new Date().toISOString();
        const { data: fresh } = await supabase
          .from("events")
          .select("id, title, starts_at, duration_min, type, source")
          .eq("user_id", userId)
          .gte("starts_at", today)
          .order("starts_at", { ascending: true })
          .limit(50);
        if (fresh) setEvents(fresh);
      } else {
        setSyncResult("Failed");
      }
    } catch {
      setSyncResult("Failed");
    }
    setIsSyncing(false);
    setTimeout(() => setSyncResult(null), 5000);
  }

  function openDetail(event: CalendarEvent) {
    setSelected(event);
    setMode("detail");
    setConfirmDelete(false);
  }

  function openEdit() {
    if (!selected) return;
    setEditTitle(selected.title);
    setEditType(selected.type);
    setEditStartsAt(toLocalDatetimeInput(selected.starts_at));
    setEditDuration(selected.duration_min);
    setMode("edit");
  }

  function closeSheet() {
    setSelected(null);
    setConfirmDelete(false);
  }

  async function saveEdit() {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/events/${selected.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editTitle,
          type: editType,
          starts_at: new Date(editStartsAt).toISOString(),
          duration_min: Number(editDuration),
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setEvents((prev) =>
          prev.map((e) => (e.id === selected.id ? { ...e, ...updated } : e))
        );
        closeSheet();
      }
    } finally {
      setSaving(false);
    }
  }

  async function deleteEvent() {
    if (!selected) return;
    setDeleting(true);
    try {
      await fetch(`/api/events/${selected.id}`, { method: "DELETE" });
      setEvents((prev) => prev.filter((e) => e.id !== selected.id));
      closeSheet();
    } finally {
      setDeleting(false);
    }
  }

  const groups = groupByDay(events);

  return (
    <>
      <div className="px-2">
        <div className="flex items-center justify-between px-2.5 py-1 mb-1">
          <span className="text-xs text-text-muted uppercase tracking-wider">Events</span>
          <button
            onClick={syncFromGoogle}
            disabled={isSyncing}
            className="flex items-center gap-1 px-1.5 py-0.5 text-xs text-text-muted hover:text-accent rounded transition-colors disabled:opacity-50"
            title="Import from Google Calendar"
          >
            <CalendarSync className={`h-3 w-3 ${isSyncing ? "animate-spin" : ""}`} />
            {syncResult && <span className="text-accent">{syncResult}</span>}
          </button>
        </div>

        {events.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No upcoming events"
            description="Your events will appear here."
          />
        ) : (
          <div className="space-y-3">
            {groups.map((group) => {
              const isExpanded = expandedDays.has(group.date);
              const visibleEvents = isExpanded ? group.events : group.events.slice(0, 3);
              const hasMore = group.events.length > 3;

              return (
                <div key={group.date}>
                  <div className="flex items-center justify-between px-2.5 mb-1">
                    <p className="text-xs font-medium text-text-muted uppercase tracking-wider">
                      {group.label}
                    </p>
                    <span className="text-xs text-text-muted/50">{group.events.length}</span>
                  </div>
                  <ul className="space-y-0.5">
                    {visibleEvents.map((event) => (
                      <li key={event.id}>
                        <button
                          onClick={() => openDetail(event)}
                          className="w-full flex items-start gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors group text-left"
                        >
                          <div
                            className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5 border ${getEventColor(event.type)}`}
                          >
                            {getEventIcon(event.type)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors">
                              {event.title}
                            </p>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <Clock className="h-3 w-3 text-text-muted" />
                              <p className="text-xs text-text-muted">
                                {formatTime(event.starts_at)}
                                {event.duration_min > 0 && ` · ${formatDuration(event.duration_min)}`}
                              </p>
                              {event.source === "google_calendar" && (
                                <span className="inline-block w-1 h-1 rounded-full bg-accent/60" aria-label="Google Calendar" />
                              )}
                            </div>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {hasMore && (
                    <button
                      onClick={() =>
                        setExpandedDays((prev) => {
                          const next = new Set(prev);
                          if (next.has(group.date)) next.delete(group.date);
                          else next.add(group.date);
                          return next;
                        })
                      }
                      className="w-full text-center py-1 text-xs text-text-muted hover:text-accent transition-colors"
                    >
                      {isExpanded ? "Show less" : `+${group.events.length - 3} more`}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Event detail / edit sheet */}
      <AnimatePresence>
        {selected && (
          <>
            {/* Backdrop */}
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={closeSheet}
              className="fixed inset-0 bg-black/50 z-40"
            />

            {/* Sheet */}
            <motion.div
              key="sheet"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              transition={{ type: "spring", stiffness: 400, damping: 35 }}
              className="fixed inset-x-4 bottom-above-nav md:bottom-6 md:left-auto md:right-6 md:w-80 bg-bg-surface border border-border-subtle rounded-2xl shadow-2xl z-50 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-border-subtle">
                <div className={`flex items-center gap-2 px-2 py-0.5 rounded-full text-xs font-medium border ${getEventColor(selected.type)}`}>
                  {getEventIcon(selected.type)}
                  <span className="capitalize">{selected.type}</span>
                </div>
                <button
                  onClick={closeSheet}
                  className="p-1.5 rounded-lg hover:bg-bg-elevated transition-colors"
                  aria-label="Close"
                >
                  <X className="h-4 w-4 text-text-muted" />
                </button>
              </div>

              {mode === "detail" ? (
                <div className="px-4 py-4 space-y-4">
                  {/* Title */}
                  <p className="text-base font-medium text-text-primary leading-snug">
                    {selected.title}
                  </p>

                  {/* Meta */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-sm text-text-secondary">
                      <Calendar className="h-3.5 w-3.5 text-text-muted shrink-0" />
                      <span>{formatDate(selected.starts_at)}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-text-secondary">
                      <Clock className="h-3.5 w-3.5 text-text-muted shrink-0" />
                      <span>
                        {formatTime(selected.starts_at)}
                        {selected.duration_min > 0 && ` · ${formatDuration(selected.duration_min)}`}
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  {confirmDelete ? (
                    <div className="space-y-2">
                      <p className="text-xs text-status-error-fg">Delete this event?</p>
                      <div className="flex gap-2">
                        <button
                          onClick={deleteEvent}
                          disabled={deleting}
                          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-status-error-bg border border-status-error-border text-status-error-fg text-sm font-medium hover:opacity-80 transition-opacity disabled:opacity-50"
                        >
                          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                          Delete
                        </button>
                        <button
                          onClick={() => setConfirmDelete(false)}
                          className="flex-1 py-2 rounded-lg bg-bg-elevated text-text-secondary text-sm hover:text-text-primary transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={openEdit}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-bg-elevated hover:bg-bg-hover text-text-secondary hover:text-text-primary text-sm transition-colors"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        Edit
                      </button>
                      <button
                        onClick={() => setConfirmDelete(true)}
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-bg-elevated hover:bg-status-error-bg text-text-secondary hover:text-status-error-fg text-sm transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="px-4 py-4 space-y-3">
                  {/* Edit form */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-text-secondary">Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      autoFocus
                      className="w-full h-9 rounded-lg bg-bg-elevated border border-border-subtle px-3 text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-text-secondary">Type</label>
                    <select
                      value={editType}
                      onChange={(e) => setEditType(e.target.value)}
                      className="w-full h-9 rounded-lg bg-bg-elevated border border-border-subtle px-3 text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
                    >
                      {EVENT_TYPES.map((t) => (
                        <option key={t} value={t} className="bg-bg-elevated capitalize">{t}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-text-secondary">Date & time</label>
                    <input
                      type="datetime-local"
                      value={editStartsAt}
                      onChange={(e) => setEditStartsAt(e.target.value)}
                      className="w-full h-9 rounded-lg bg-bg-elevated border border-border-subtle px-3 text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-text-secondary">Duration (minutes)</label>
                    <input
                      type="number"
                      min={0}
                      value={editDuration}
                      onChange={(e) => setEditDuration(Number(e.target.value))}
                      className="w-full h-9 rounded-lg bg-bg-elevated border border-border-subtle px-3 text-sm text-text-primary focus:outline-none focus:border-accent transition-colors"
                    />
                  </div>

                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={saveEdit}
                      disabled={saving || !editTitle.trim()}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium disabled:opacity-50 transition-colors"
                    >
                      {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                      Save
                    </button>
                    <button
                      onClick={() => setMode("detail")}
                      className="flex-1 py-2 rounded-lg bg-bg-elevated text-text-secondary text-sm hover:text-text-primary transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
