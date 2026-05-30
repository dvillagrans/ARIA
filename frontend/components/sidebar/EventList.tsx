"use client";

/**
 * EventList — upcoming events with Realtime updates.
 *
 * Subscribes to a per-user events channel. Updates list on INSERT/UPDATE/DELETE.
 *
 * Spec §7: per-user Realtime channel for events.
 * ADR-06.
 */

import { useState } from "react";
import { useRealtime } from "@/lib/hooks/use-realtime";

export interface CalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  duration_min: number;
  type: string;
}

interface EventListProps {
  userId: string;
  initialEvents?: CalendarEvent[];
}

export default function EventList({
  userId,
  initialEvents = [],
}: EventListProps) {
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
      <p className="text-xs text-gray-500 px-3 py-2">No upcoming events.</p>
    );
  }

  return (
    <ul className="space-y-1">
      {events.map((event) => (
        <li
          key={event.id}
          className="px-3 py-2 rounded-lg hover:bg-gray-800 transition-colors"
        >
          <p className="text-sm text-gray-200 truncate">{event.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
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
