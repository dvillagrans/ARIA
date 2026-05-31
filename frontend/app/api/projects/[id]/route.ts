/**
 * PATCH /api/projects/[id] — update a project's editable fields.
 *
 * Only a whitelist of fields is accepted (name, color, links, context) to
 * prevent mass-assignment of user_id / is_active. The `links` payload is
 * validated as an array of { label, url } where url must be http(s) to avoid
 * storing javascript:/data: URLs that would XSS when rendered as anchors.
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

interface ProjectLink {
  label: string;
  url: string;
}

function sanitizeLinks(value: unknown): ProjectLink[] | null {
  if (!Array.isArray(value)) return null;
  const links: ProjectLink[] = [];
  for (const raw of value) {
    if (typeof raw !== "object" || raw === null) return null;
    const { label, url } = raw as Record<string, unknown>;
    if (typeof label !== "string" || typeof url !== "string") return null;

    const trimmedUrl = url.trim();
    let parsed: URL;
    try {
      parsed = new URL(trimmedUrl);
    } catch {
      return null;
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    links.push({ label: label.trim(), url: trimmedUrl });
  }
  return links;
}

export async function PATCH(
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

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patch: Record<string, unknown> = {};

  if ("name" in body) {
    const name = typeof body.name === "string" ? body.name.trim() : "";
    if (!name) {
      return NextResponse.json({ error: "name cannot be empty" }, { status: 400 });
    }
    patch.name = name;
  }

  if ("color" in body) {
    if (typeof body.color !== "string") {
      return NextResponse.json({ error: "color must be a string" }, { status: 400 });
    }
    patch.color = body.color;
  }

  if ("context" in body) {
    if (body.context !== null && typeof body.context !== "string") {
      return NextResponse.json({ error: "context must be a string" }, { status: 400 });
    }
    patch.context = body.context;
  }

  if (typeof body.github_repo === "string") patch.github_repo = body.github_repo;

  if ("links" in body) {
    const links = sanitizeLinks(body.links);
    if (links === null) {
      return NextResponse.json(
        { error: "links must be an array of { label, url } with http(s) URLs" },
        { status: 400 }
      );
    }
    patch.links = links;
  }

  if (Object.keys(patch).length === 0) {
    return NextResponse.json({ error: "No valid fields to update" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("projects")
    .update(patch)
    .eq("id", id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }

  return NextResponse.json(data);
}
