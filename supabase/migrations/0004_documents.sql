-- Storage bucket for project documents
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'project-documents',
  'project-documents',
  false,
  10485760, -- 10 MB
  ARRAY[
    'application/pdf',
    'text/plain',
    'text/markdown',
    'text/x-markdown'
  ]
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: users can only access their own files (path starts with user_id)
CREATE POLICY "documents_upload"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'project-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "documents_read"
  ON storage.objects FOR SELECT TO authenticated
  USING (
    bucket_id = 'project-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

CREATE POLICY "documents_delete"
  ON storage.objects FOR DELETE TO authenticated
  USING (
    bucket_id = 'project-documents'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Documents table: tracks uploaded files and processing status
CREATE TABLE public.documents (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid        NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
  user_id      uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  name         text        NOT NULL,
  storage_path text        NOT NULL,
  mime_type    text,
  size_bytes   bigint,
  status       text        NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'processing', 'done', 'error')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_project ON public.documents (project_id);
CREATE INDEX idx_documents_user    ON public.documents (user_id);

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_owner
  ON public.documents FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
