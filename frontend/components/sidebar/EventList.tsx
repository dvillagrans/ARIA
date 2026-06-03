"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  CalendarDays,
  CalendarSync,
  Clock,
  Users,
  GraduationCap,
  Stethoscope,
  Calendar,
  ChevronDown,
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

type DayTier = "today" | "tomorrow" | "this-week" | "later";

interface DayGroup {
  label: string;
  date: string;
  tier: DayTier;
  events: CalendarEvent[];
}

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = "aria:expanded-days";

function loadExpanded(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {
    /* ignore */
  }
  return new Set();
}

function saveExpanded(ids: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// Grouping
// ---------------------------------------------------------------------------

function groupByDay(events: CalendarEvent[]): DayGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const endOfWeek = new Date(today);
  endOfWeek.setDate(endOfWeek.getDate() + (7 - today.getDay()));

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
    let tier: DayTier;

    if (eventDay.getTime() === today.getTime()) {
      label = "Today";
      tier = "today";
    } else if (eventDay.getTime() === tomorrow.getTime()) {
      label = "Tomorrow";
      tier = "tomorrow";
    } else if (eventDay <= endOfWeek) {
      label = eventDate.toLocaleDateString("en-US", { weekday: "long" });
      tier = "this-week";
    } else {
      label = eventDate.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
      tier = "later";
    }

    if (!groups.has(key)) {
      groups.set(key, { label, date: key, tier, events: [] });
    }
    groups.get(key)!.events.push(event);
  }

  return Array.from(groups.values());
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getEventIcon(type: string) {
  switch (type) {
    case "meeting":
      return <Users className="h-3.5 w-3.5" />;
    case "class":
      return <GraduationCap className="h-3.5 w-3.5" />;
    case "appointment":
      return <Stethoscope className="h-3.5 w-3.5" />;
    default:
      return <Calendar className="h-3.5 w-3.5" />;
  }
}

function getEventColor(type: string): string {
  switch (type) {
    case "meeting":
      return "bg-blue-500/15 text-blue-400 border-blue-500/20";
    case "class":
      return "bg-purple-500/15 text-purple-400 border-purple-500/20";
    case "appointment":
      return "bg-rose-500/15 text-rose-400 border-rose-500/20";
    default:
      return "bg-accent/15 text-accent border-accent/20";
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(min: number): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h${m}m` : `${h}h`;
}

// ---------------------------------------------------------------------------
// EventItem — shared between expanded & collapsed
// ---------------------------------------------------------------------------

function EventItem({ event }: { event: CalendarEvent }) {
  return (
    <li className="flex items-start gap-2.5 px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors group">
      <div
        className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5 border ${getEventColor(
          event.type
        )}`}
      >
        {getEventIcon(event.type)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors">
          {event.title}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <Clock className="h-2.5 w-2.5 text-text-muted" />
          <p className="text-[10px] text-text-muted">
            {formatTime(event.starts_at)}
            {event.duration_min > 0 &&
              ` · ${formatDuration(event.duration_min)}`}
          </p>
          {event.source === "google_calendar" && (
            <span className="text-[10px] text-accent/60">📅</span>
          )}
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function EventList({
  userId,
  initialEvents = [],
}: EventListProps) {
  const [events, setEvents] = useState<CalendarEvent[]>(initialEvents);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());
  const [showLater, setShowLater] = useState(false);

  // Load expanded state from localStorage on mount
  useEffect(() => {
    setExpandedDays(loadExpanded());
  }, []);

  // Persist expanded state changes
  const toggleDay = (date: string) => {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(date)) {
        next.delete(date);
      } else {
        next.add(date);
      }
      saveExpanded(next);
      return next;
    });
  };

  // Realtime
  useRealtime<CalendarEvent>(
    [{ table: "events", filter: `user_id=eq.${userId}` }],
    (_table, eventType, row) => {
      setEvents((prev) => {
        if (eventType === "INSERT") {
          return [...prev, row].sort(
            (a, b) =>
              new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
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

  // Polling fallback
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

  // Sync from Google Calendar
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

  // Group events
  const groups = groupByDay(events);
  const immediateGroups = groups.filter(
    (g) => g.tier === "today" || g.tier === "tomorrow"
  );
  const weekGroups = groups.filter((g) => g.tier === "this-week");
  const laterGroups = groups.filter((g) => g.tier === "later");

  const laterEventCount = laterGroups.reduce(
    (sum, g) => sum + g.events.length,
    0
  );

  return (
    <div className="px-2">
      <div className="flex items-center justify-between px-2.5 py-1 mb-1">
        <span className="text-[10px] text-text-muted uppercase tracking-wider">
          Events
        </span>
        <button
          onClick={syncFromGoogle}
          disabled={isSyncing}
          className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-text-muted hover:text-accent rounded transition-colors disabled:opacity-50"
          title="Import from Google Calendar"
        >
          <CalendarSync
            className={`h-3 w-3 ${isSyncing ? "animate-spin" : ""}`}
          />
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
        <div className="space-y-1">
          {/* ── Today & Tomorrow — always expanded ── */}
          {immediateGroups.map((group) => (
            <div key={group.date}>
              <p className="text-[10px] font-semibold text-accent px-2.5 mb-1">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.events.map((event) => (
                  <EventItem key={event.id} event={event} />
                ))}
              </ul>
            </div>
          ))}

          {/* ── This week — collapsed by default ── */}
          {weekGroups.map((group) => {
            const isExpanded = expandedDays.has(group.date);
            return (
              <div key={group.date}>
                <button
                  onClick={() => toggleDay(group.date)}
                  className="w-full flex items-center justify-between px-2.5 py-1 rounded-md hover:bg-bg-elevated transition-colors"
                >
                  <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                    {group.label}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-text-muted/50">
                      {group.events.length}
                    </span>
                    <ChevronDown
                      className={`h-3 w-3 text-text-muted transition-transform ${
                        isExpanded ? "rotate-180" : ""
                      }`}
                    />
                  </div>
                </button>
                {isExpanded && (
                  <ul className="space-y-0.5">
                    {group.events.map((event) => (
                      <EventItem key={event.id} event={event} />
                    ))}
                  </ul>
                )}
              </div>
            );
          })}

          {/* ── Later — hidden behind "show more" ── */}
          {laterGroups.length > 0 && (
            <>
              {showLater &&
                laterGroups.map((group) => {
                  const isExpanded = expandedDays.has(group.date);
                  return (
                    <div key={group.date}>
                      <button
                        onClick={() => toggleDay(group.date)}
                        className="w-full flex items-center justify-between px-2.5 py-1 rounded-md hover:bg-bg-elevated transition-colors"
                      >
                        <span className="text-[10px] font-medium text-text-muted uppercase tracking-wider">
                          {group.label}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-text-muted/50">
                            {group.events.length}
                          </span>
                          <ChevronDown
                            className={`h-3 w-3 text-text-muted transition-transform ${
                              isExpanded ? "rotate-180" : ""
                            }`}
                          />
                        </div>
                      </button>
                      {isExpanded && (
                        <ul className="space-y-0.5">
                          {group.events.map((event) => (
                            <EventItem key={event.id} event={event} />
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
              <button
                onClick={() => setShowLater((v) => !v)}
                className="w-full text-center py-1.5 text-[10px] text-text-muted hover:text-accent transition-colors"
              >
                {showLater
                  ? "Hide later events"
                  : `show ${laterGroups.length} more days · ${laterEventCount} events`}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
