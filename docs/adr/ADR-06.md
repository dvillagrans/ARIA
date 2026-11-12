# ADR-06: One Realtime channel per filter, with a monotonic topic suffix

Referenced as `ADR-06` in `frontend/lib/hooks/use-realtime.ts`.

## Context

The `useRealtime` hook subscribes to Supabase Realtime per filter (project
tasks, per-user events/reminders/notes) and must survive React StrictMode
remounts. `supabase.channel(topic)` deduplicates by topic and returns an
existing channel: under StrictMode the async `removeChannel()` cleanup has
not evicted the old (already-joined) channel before the remount re-runs, so
a stable topic would hand back a joined channel and
`.on("postgres_changes")` would throw.

## Decision

Create one channel per `RealtimeFilter` entry, with a monotonic suffix so
each subscription gets a distinct channel topic; clean up all channels on
unmount via the `useEffect` return.

## Reason

Distinct topics avoid the StrictMode re-join race; per-filter channels keep
subscriptions scoped and cleanup simple.
