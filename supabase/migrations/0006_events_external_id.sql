-- Migration 0006: Add external_id to events for Google Calendar sync

ALTER TABLE public.events
ADD COLUMN IF NOT EXISTS external_id text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_user_external_id
ON public.events (user_id, external_id)
WHERE external_id IS NOT NULL;
