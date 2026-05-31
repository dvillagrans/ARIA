import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

function maskToken(token: string): string {
  if (!token) return "";
  if (token.length <= 4) return "****";
  return `****${token.slice(-4)}`;
}

export async function GET(): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data } = await supabase
    .from("connector_state")
    .select("state_json")
    .eq("user_id", user.id)
    .eq("provider", "github")
    .maybeSingle();

  const stateJson = data?.state_json as Record<string, unknown> | null;
  const token = typeof stateJson?.token === "string" ? stateJson.token : "";

  return NextResponse.json({
    connected: !!token,
    masked: maskToken(token),
  });
}

const GITHUB_TOKEN_RE = /^(ghp_|github_pat_|[a-f0-9]{40})/i;

export async function PATCH(req: Request): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  if (!body || typeof body.token !== "string") {
    return NextResponse.json({ error: "token is required and must be a string." }, { status: 400 });
  }

  const trimmedToken = body.token.trim();

  if (trimmedToken && !GITHUB_TOKEN_RE.test(trimmedToken)) {
    return NextResponse.json({ error: "Invalid GitHub token format." }, { status: 400 });
  }

  const { data: existing } = await supabase
    .from("connector_state")
    .select("state_json")
    .eq("user_id", user.id)
    .eq("provider", "github")
    .maybeSingle();

  const existingState = (existing?.state_json as Record<string, unknown>) ?? {};
  const newState = { ...existingState, token: trimmedToken };

  const now = new Date().toISOString();
  const { error: upsertError } = await supabase
    .from("connector_state")
    .upsert(
      {
        user_id: user.id,
        provider: "github",
        state_json: newState,
        updated_at: now,
      },
      { onConflict: "user_id,provider" }
    );

  if (upsertError) {
    return NextResponse.json({ error: upsertError.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
