"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { CalendarDays, CalendarSync } from "lucide-react";
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

export default function EventList({ userId, initialEvents = [] }: EventListProps) {
  const [events, setEvents] = useState<CalendarEvent[]>(initialEvents);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);

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
        .limit(20);
      if (data) {
        setEvents(data);
      }
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
        setSyncResult(`+${data.imported} new, ${data.updated} updated`);
        // Refresh events after sync
        const supabase = createClient();
        const today = new Date().toISOString();
        const { data: fresh } = await supabase
          .from("events")
          .select("id, title, starts_at, duration_min, type, source")
          .eq("user_id", userId)
          .gte("starts_at", today)
          .order("starts_at", { ascending: true })
          .limit(20);
        if (fresh) setEvents(fresh);
      } else {
        setSyncResult("Sync failed");
      }
    } catch {
      setSyncResult("Sync failed");
    }
    setIsSyncing(false);
    setTimeout(() => setSyncResult(null), 5000);
  }

  return (
    <div className="px-2">
      <div className="flex items-center justify-between px-2.5 py-1 mb-1">
        <span className="text-[10px] text-text-muted uppercase tracking-wider">Events</span>
        <button
          onClick={syncFromGoogle}
          disabled={isSyncing}
          className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-text-muted hover:text-accent rounded transition-colors disabled:opacity-50"
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
          description="Your next 7 days of events will appear here."
        />
      ) : (
        <ul className="space-y-0.5">
          {events.map((event) => (
            <li
              key={event.id}
              className="px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors group"
            >
              <p className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors">
                {event.title}
              </p>
              <p className="text-[10px] text-text-muted mt-0.5">
                {new Date(event.starts_at).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                {event.duration_min > 0 && ` · ${event.duration_min}m`}
                {event.source === "google_calendar" && (
                  <span className="ml-1 text-accent">📅</span>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
