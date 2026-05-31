"use client";

import { useState } from "react";
import { CalendarDays } from "lucide-react";
import { useRealtime } from "@/lib/hooks/use-realtime";
import EmptyState from "@/components/ui/EmptyState";

export interface CalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  duration_min: number;
  type: string;
  [key: string]: unknown;
}

interface EventListProps {
  userId: string;
  initialEvents?: CalendarEvent[];
}

export default function EventList({ userId, initialEvents = [] }: EventListProps) {
  const [events, setEvents] = useState<CalendarEvent[]>(initialEvents);

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

  if (events.length === 0) {
    return (
      <EmptyState
        icon={CalendarDays}
        title="No upcoming events"
        description="Your next 7 days of events will appear here."
      />
    );
  }

  return (
    <ul className="space-y-0.5 px-2">
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
          </p>
        </li>
      ))}
    </ul>
  );
}
