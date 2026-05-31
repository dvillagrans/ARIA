-- =====================================================================
-- ARIA — Phase 7: project-scoped conversations
-- =====================================================================

ALTER TABLE public.conversations
  ADD COLUMN project_id uuid REFERENCES public.projects(id) ON DELETE CASCADE;

-- Partial index: only index rows that belong to a project (NULL rows use the
-- existing idx_conversations_user_created index for general chat queries).
CREATE INDEX idx_conversations_user_project_created
  ON public.conversations (user_id, project_id, created_at DESC)
  WHERE project_id IS NOT NULL;
