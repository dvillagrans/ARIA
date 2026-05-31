-- Migration 0005: Add calendar_event_id to reminders for Google Calendar sync

ALTER TABLE public.reminders
ADD COLUMN IF NOT EXISTS calendar_event_id text;

CREATE INDEX IF NOT EXISTS idx_reminders_calendar_event_id
ON public.reminders (calendar_event_id)
WHERE calendar_event_id IS NOT NULL;
