"use client";

/**
 * useRealtime — Supabase Realtime subscription hook.
 *
 * ADR-06: Creates one channel per RealtimeFilter entry. Cleans up all
 * channels on unmount via useEffect return. Supports per-project task
 * channels and per-user event/reminder/note channels.
 *
 * Spec §7: channel cleanup on unmount.
 */

import { useEffect } from "react";
import { createClient } from "@/lib/supabase/client";

export interface RealtimeFilter {
  /** Postgres table name to subscribe to (e.g. "tasks", "events"). */
  table: string;
  /** Schema name, defaults to "public". */
  schema?: string;
  /**
   * Row-level filter expression in Supabase Realtime filter syntax.
   * Example: "project_id=eq.{uuid}" or "user_id=eq.{uuid}"
   */
  filter?: string;
}

export function useRealtime<T extends object>(
  filters: RealtimeFilter[],
  onEvent: (
    table: string,
    eventType: "INSERT" | "UPDATE" | "DELETE",
    row: T
  ) => void
): void {
  useEffect(() => {
    if (filters.length === 0) return;

    const supabase = createClient();
    const channels = filters.map((f) => {
      const channelName = `realtime-${f.table}-${f.filter ?? "all"}`;
      const channel = supabase.channel(channelName);

      const pgChanges: {
        event: "*";
        schema: string;
        table: string;
        filter?: string;
      } = {
        event: "*",
        schema: f.schema ?? "public",
        table: f.table,
      };
      if (f.filter) {
        pgChanges.filter = f.filter;
      }

      channel
        .on(
          "postgres_changes" as Parameters<typeof channel.on>[0],
          pgChanges as Parameters<typeof channel.on>[1],
          (payload: {
            eventType: "INSERT" | "UPDATE" | "DELETE";
            new: T;
            old: T;
          }) => {
            const row =
              payload.eventType === "DELETE" ? payload.old : payload.new;
            onEvent(f.table, payload.eventType, row);
          }
        )
        .subscribe();

      return channel;
    });

    // Cleanup: unsubscribe all channels on unmount.
    return () => {
      channels.forEach((ch) => supabase.removeChannel(ch));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);
}
