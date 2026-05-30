-- =====================================================================
-- ARIA — Schema completo (Phases 0–4 unificados)
-- =====================================================================

-- =====================================================================
-- 1. Extensions
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector    WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto  WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =====================================================================
-- 2. Enums
-- =====================================================================
CREATE TYPE public.task_status       AS ENUM ('pending', 'in_progress', 'done', 'cancelled');
CREATE TYPE public.task_energy       AS ENUM ('low', 'medium', 'high');
CREATE TYPE public.event_type        AS ENUM ('meeting', 'class', 'appointment', 'other');
CREATE TYPE public.conversation_role AS ENUM ('user', 'assistant');

-- =====================================================================
-- 3. Trigger helper
-- =====================================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- =====================================================================
-- 4. Tables
-- =====================================================================

-- 4.1 users
CREATE TABLE public.users (
  id          uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name        text,
  timezone    text        NOT NULL DEFAULT 'UTC',
  preferences jsonb       NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- 4.2 projects
CREATE TABLE public.projects (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  name       text        NOT NULL,
  color      text        NOT NULL DEFAULT '#888888',
  context    text,
  is_active  boolean     NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_projects_user_active ON public.projects (user_id, is_active);

-- 4.3 tasks
CREATE TABLE public.tasks (
  id           uuid               PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid               NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  title        text               NOT NULL,
  description  text,
  status       public.task_status NOT NULL DEFAULT 'pending',
  priority     smallint           NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  energy_level public.task_energy NOT NULL DEFAULT 'medium',
  deadline     timestamptz,
  context_note text,
  source       text               NOT NULL DEFAULT 'manual',
  external_id  text,
  embedding    vector(4096),
  created_at   timestamptz        NOT NULL DEFAULT now(),
  updated_at   timestamptz        NOT NULL DEFAULT now()
);
CREATE INDEX idx_tasks_project_status ON public.tasks (project_id, status);
CREATE INDEX idx_tasks_deadline       ON public.tasks (deadline) WHERE deadline IS NOT NULL;
CREATE UNIQUE INDEX tasks_source_external_id_idx
  ON public.tasks (source, external_id) WHERE external_id IS NOT NULL;

-- 4.4 events
CREATE TABLE public.events (
  id           uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid              REFERENCES public.projects(id) ON DELETE SET NULL,
  user_id      uuid              NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  title        text              NOT NULL,
  starts_at    timestamptz       NOT NULL,
  duration_min integer           NOT NULL DEFAULT 60 CHECK (duration_min > 0),
  type         public.event_type NOT NULL DEFAULT 'other',
  recurrence   jsonb,
  source       text              NOT NULL DEFAULT 'manual',
  external_id  text,
  embedding    vector(4096),
  created_at   timestamptz       NOT NULL DEFAULT now(),
  updated_at   timestamptz       NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_user_starts ON public.events (user_id, starts_at);
CREATE UNIQUE INDEX events_source_external_id_idx
  ON public.events (source, external_id) WHERE external_id IS NOT NULL;

-- 4.5 reminders
CREATE TABLE public.reminders (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid        REFERENCES public.projects(id) ON DELETE SET NULL,
  user_id     uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  title       text        NOT NULL,
  due_at      timestamptz NOT NULL,
  amount      numeric(12,2),
  currency    char(3),
  recurrence  jsonb,
  is_done     boolean     NOT NULL DEFAULT false,
  source      text        NOT NULL DEFAULT 'aria_chat',
  external_id text,
  embedding   vector(4096),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_reminders_user_due ON public.reminders (user_id, due_at)
  WHERE is_done = false;
CREATE UNIQUE INDEX reminders_source_external_id_idx
  ON public.reminders (source, external_id) WHERE external_id IS NOT NULL;

-- 4.6 notes
CREATE TABLE public.notes (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid        REFERENCES public.projects(id) ON DELETE SET NULL,
  user_id     uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  content     text        NOT NULL,
  tags        text[]      NOT NULL DEFAULT '{}',
  source      text        NOT NULL DEFAULT 'manual',
  external_id text,
  embedding   vector(4096),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX notes_source_external_id_idx
  ON public.notes (source, external_id) WHERE external_id IS NOT NULL;

-- 4.7 conversations
CREATE TABLE public.conversations (
  id         uuid                     PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid                     NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role       public.conversation_role NOT NULL,
  content    text                     NOT NULL,
  metadata   jsonb                    NOT NULL DEFAULT '{}'::jsonb,
  embedding  vector(4096),
  created_at timestamptz              NOT NULL DEFAULT now(),
  updated_at timestamptz              NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_user_created ON public.conversations (user_id, created_at DESC);

-- 4.8 briefings
CREATE TABLE public.briefings (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  date           date        NOT NULL,
  content        text        NOT NULL,
  invalidated_at timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);

-- 4.9 connector_state
CREATE TABLE public.connector_state (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  provider   text        NOT NULL,
  state_json jsonb       NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, provider)
);

-- Embedding indexes omitidos: pgvector HNSW soporta máximo 2000 dims.
-- Con un solo usuario el sequential scan es suficiente.

-- =====================================================================
-- 6. updated_at triggers
-- =====================================================================
CREATE TRIGGER trg_projects_updated_at
  BEFORE UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_tasks_updated_at
  BEFORE UPDATE ON public.tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_events_updated_at
  BEFORE UPDATE ON public.events
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_reminders_updated_at
  BEFORE UPDATE ON public.reminders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_notes_updated_at
  BEFORE UPDATE ON public.notes
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_conversations_updated_at
  BEFORE UPDATE ON public.conversations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_briefings_updated_at
  BEFORE UPDATE ON public.briefings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =====================================================================
-- 7. Auth trigger: auto-create public.users + Personal project
-- =====================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.users (id, name, timezone)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
    COALESCE(NEW.raw_user_meta_data->>'timezone', 'UTC')
  )
  ON CONFLICT (id) DO NOTHING;

  IF NOT EXISTS (
    SELECT 1 FROM public.projects
    WHERE user_id = NEW.id AND name = 'Personal'
  ) THEN
    INSERT INTO public.projects (user_id, name, color, context, is_active)
    VALUES (NEW.id, 'Personal', '#6366f1', 'Personal tasks and reminders', true);
  END IF;

  RETURN NEW;
END $$;

CREATE TRIGGER trg_on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =====================================================================
-- 8. Row Level Security
-- =====================================================================
ALTER TABLE public.users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminders        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.briefings        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connector_state  ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_self
  ON public.users FOR ALL TO authenticated
  USING (id = auth.uid()) WITH CHECK (id = auth.uid());

CREATE POLICY projects_owner
  ON public.projects FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY events_owner
  ON public.events FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY reminders_owner
  ON public.reminders FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY notes_owner
  ON public.notes FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY conversations_owner
  ON public.conversations FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY briefings_owner
  ON public.briefings FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY connector_state_owner
  ON public.connector_state FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- tasks: RLS chained a través de projects (tasks no tiene user_id)
CREATE POLICY tasks_owner
  ON public.tasks FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.projects p
      WHERE p.id = tasks.project_id AND p.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.projects p
      WHERE p.id = tasks.project_id AND p.user_id = auth.uid()
    )
  );

-- =====================================================================
-- 9. Functions
-- =====================================================================

-- 9.1 match_all_embeddings — RAG: 5 branches con project_id/name
CREATE OR REPLACE FUNCTION public.match_all_embeddings(
  query_embedding vector(4096),
  match_threshold float DEFAULT 0.5,
  match_count     int   DEFAULT 10
)
RETURNS TABLE (
  id           uuid,
  source_table text,
  content      text,
  similarity   float,
  project_id   uuid,
  project_name text
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, extensions AS $$
  SELECT t.id, 'tasks'::text,
    COALESCE(t.title, '') || COALESCE(' — ' || t.description, ''),
    1 - (t.embedding <=> query_embedding), p.id, p.name
  FROM public.tasks t
  JOIN public.projects p ON p.id = t.project_id
  WHERE t.embedding IS NOT NULL
    AND 1 - (t.embedding <=> query_embedding) >= match_threshold

  UNION ALL

  SELECT n.id, 'notes'::text, n.content,
    1 - (n.embedding <=> query_embedding), p.id, p.name
  FROM public.notes n
  LEFT JOIN public.projects p ON p.id = n.project_id
  WHERE n.embedding IS NOT NULL
    AND 1 - (n.embedding <=> query_embedding) >= match_threshold

  UNION ALL

  SELECT e.id, 'events'::text, e.title,
    1 - (e.embedding <=> query_embedding), p.id, p.name
  FROM public.events e
  LEFT JOIN public.projects p ON p.id = e.project_id
  WHERE e.embedding IS NOT NULL
    AND 1 - (e.embedding <=> query_embedding) >= match_threshold

  UNION ALL

  SELECT r.id, 'reminders'::text, r.title,
    1 - (r.embedding <=> query_embedding), p.id, p.name
  FROM public.reminders r
  LEFT JOIN public.projects p ON p.id = r.project_id
  WHERE r.embedding IS NOT NULL
    AND 1 - (r.embedding <=> query_embedding) >= match_threshold

  UNION ALL

  SELECT c.id, 'conversations'::text, c.content,
    1 - (c.embedding <=> query_embedding), NULL::uuid, NULL::text
  FROM public.conversations c
  WHERE c.role = 'user'
    AND c.embedding IS NOT NULL
    AND 1 - (c.embedding <=> query_embedding) >= match_threshold

  ORDER BY 4 DESC
  LIMIT match_count;
$$;

-- 9.2 search_tasks_by_similarity — fuzzy search via pg_trgm
CREATE OR REPLACE FUNCTION public.search_tasks_by_similarity(
  p_user_id   uuid,
  p_reference text,
  p_threshold float DEFAULT 0.3
)
RETURNS SETOF public.tasks
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, extensions AS $$
  SELECT t.*
  FROM public.tasks t
  JOIN public.projects p ON p.id = t.project_id
  WHERE p.user_id = p_user_id
    AND similarity(t.title, p_reference) > p_threshold
  ORDER BY similarity(t.title, p_reference) DESC
  LIMIT 1;
$$;

-- 9.3 correct_record — atomic delete + insert para correcciones
CREATE OR REPLACE FUNCTION public.correct_record(
  old_table text,
  old_id    uuid,
  new_table text,
  payload   jsonb
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  new_id   uuid;
  col      text;
  col_list text[];
  val_list text[];
BEGIN
  new_id := gen_random_uuid();

  EXECUTE format('DELETE FROM public.%I WHERE id = $1', old_table)
    USING old_id;

  FOR col IN SELECT jsonb_object_keys(payload) LOOP
    col_list := array_append(col_list, quote_ident(col));
    val_list := array_append(val_list, format('($3->>'||quote_literal(col)||')'));
  END LOOP;

  EXECUTE format(
    'INSERT INTO public.%I (id, %s) VALUES ($2, %s)',
    new_table,
    array_to_string(col_list, ', '),
    array_to_string(val_list, ', ')
  )
  USING old_id, new_id, payload;

  RETURN new_id;
END $$;

-- =====================================================================
-- 10. Seed: usuario inicial
-- Cambiá el email y la contraseña antes de usar en producción.
-- =====================================================================
DO $$
DECLARE
  v_uid uuid;
BEGIN
  -- Insert the auth user only if the email does not already exist.
  INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_user_meta_data,
    created_at,
    updated_at,
    confirmation_token,
    email_change,
    email_change_token_new,
    recovery_token
  ) VALUES (
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    'dvillagrans@aria.local',
    crypt('admin', gen_salt('bf')),
    now(),
    jsonb_build_object('name', 'dvillagrans'),
    now(),
    now(),
    '', '', '', ''
  )
  ON CONFLICT DO NOTHING;

  -- Resolve the real UID regardless of whether INSERT ran or was skipped.
  SELECT id INTO v_uid FROM auth.users WHERE email = 'dvillagrans@aria.local';

  -- Ensure public.users row exists (trigger may have already created it).
  INSERT INTO public.users (id, name, timezone)
  VALUES (v_uid, 'dvillagrans', 'UTC')
  ON CONFLICT (id) DO NOTHING;

  -- Ensure Personal project exists.
  IF NOT EXISTS (
    SELECT 1 FROM public.projects WHERE user_id = v_uid AND name = 'Personal'
  ) THEN
    INSERT INTO public.projects (user_id, name, color, context, is_active)
    VALUES (v_uid, 'Personal', '#6366f1', 'Personal tasks and reminders', true);
  END IF;
END $$;

-- =====================================================================
-- 11. Grants (restaurar permisos por defecto de Supabase)
-- =====================================================================
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES    IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES  IN SCHEMA public TO postgres, anon, authenticated, service_role;
