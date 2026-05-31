-- =====================================================================
-- ARIA — Project info: external links per project
-- =====================================================================
-- Adds a `links` column to store reference links (repository, docs, etc.)
-- as an array of { "label": text, "url": text } objects.
-- Notes/description reuse the existing `context` column.

ALTER TABLE public.projects
  ADD COLUMN links jsonb NOT NULL DEFAULT '[]'::jsonb;
