-- Migration 0004: external_id columns + connector_state table
-- Phase 4 — Connectors dedup and state tracking.

-- external_id columns (nullable on all four tables)
ALTER TABLE tasks     ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE events    ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE notes     ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS external_id TEXT;

-- reminders.source — added conditionally in case it was added manually before
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'aria_chat';

-- Partial unique indexes for dedup (only when external_id IS NOT NULL)
CREATE UNIQUE INDEX IF NOT EXISTS tasks_source_external_id_idx
  ON tasks (source, external_id) WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS events_source_external_id_idx
  ON events (source, external_id) WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS notes_source_external_id_idx
  ON notes (source, external_id) WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS reminders_source_external_id_idx
  ON reminders (source, external_id) WHERE external_id IS NOT NULL;

-- connector_state: incremental sync cursors per provider per user
CREATE TABLE IF NOT EXISTS connector_state (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    provider    TEXT NOT NULL,          -- "github" | "gmail" | "google_calendar"
    state_json  JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);
