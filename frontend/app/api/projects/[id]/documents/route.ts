import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const ALLOWED_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
]);

const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const { id } = await params;
  const supabase = await createClient();

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();
  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: project } = await supabase
    .from("projects")
    .select("id")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();
  if (!project) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json({ error: "Invalid form data" }, { status: 400 });
  }

  const file = formData.get("file") as File | null;
  if (!file) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const mimeOk =
    ALLOWED_TYPES.has(file.type) ||
    ext === "md" ||
    ext === "txt" ||
    ext === "pdf";

  if (!mimeOk) {
    return NextResponse.json(
      { error: "Unsupported file type. Use PDF, TXT, or Markdown." },
      { status: 400 }
    );
  }

  if (file.size > MAX_SIZE) {
    return NextResponse.json({ error: "File too large. Max 10 MB." }, { status: 400 });
  }

  const safeName = file.name.replace(/[^a-zA-Z0-9._\-]/g, "_");
  const storagePath = `${user.id}/${id}/${Date.now()}_${safeName}`;

  const bytes = await file.arrayBuffer();
  const { error: uploadError } = await supabase.storage
    .from("project-documents")
    .upload(storagePath, bytes, { contentType: file.type, upsert: false });

  if (uploadError) {
    return NextResponse.json(
      { error: `Upload failed: ${uploadError.message}` },
      { status: 500 }
    );
  }

  const { data: doc, error: dbError } = await supabase
    .from("documents")
    .insert({
      project_id: id,
      user_id: user.id,
      name: file.name,
      storage_path: storagePath,
      mime_type: file.type || `text/${ext}`,
      size_bytes: file.size,
      status: "pending",
    })
    .select("id")
    .single();

  if (dbError || !doc) {
    return NextResponse.json({ error: "Failed to save document record" }, { status: 500 });
  }

  // Trigger backend processing (fire and forget)
  const fastApiBase = process.env.FASTAPI_BASE_URL;
  if (fastApiBase) {
    fetch(
      `${fastApiBase}/documents/process?document_id=${doc.id}&user_id=${user.id}`,
      { method: "POST" }
    ).catch(() => {/* backend may be unavailable; status stays 'pending' */});
  }

  return NextResponse.json({ id: doc.id, name: file.name });
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const { id } = await params;
  const supabase = await createClient();

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();
  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: project } = await supabase
    .from("projects")
    .select("id")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();
  if (!project) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const { data: docs } = await supabase
    .from("documents")
    .select("id, name, mime_type, size_bytes, status, created_at")
    .eq("project_id", id)
    .order("created_at", { ascending: false })
    .limit(20);

  return NextResponse.json({ documents: docs ?? [] });
}
