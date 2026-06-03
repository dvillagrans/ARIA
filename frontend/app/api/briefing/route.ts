/**
 * GET /api/briefing — server-side proxy route.
 *
 * Reads the authenticated user's session server-side, then forwards
 * to FastAPI GET /briefing?user_id={userId}. The browser never sends
 * user_id directly — this handler injects it from the Supabase session.
 *
 * Returns BriefingResponse JSON:
 *   { content: string, cached: boolean, stale: boolean, date: string, generated_at: string }
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function GET(): Promise<Response> {
  // 1. Authenticate the caller via Supabase session (server-side).
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. Forward to FastAPI with user_id injected server-side.
  let fastapiResponse: Response;
  try {
    fastapiResponse = await fetch(
      `${FASTAPI_BASE_URL}/briefing?user_id=${user.id}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("[api/briefing] FastAPI unreachable:", err);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 503 }
    );
  }

  // 3. Return FastAPI BriefingResponse as-is.
  if (!fastapiResponse.ok) {
    const text = await fastapiResponse.text().catch(() => "Backend error");
    console.error("[api/briefing] FastAPI error:", fastapiResponse.status, text);
    return NextResponse.json(
      { error: text },
      { status: fastapiResponse.status }
    );
  }

  const data = await fastapiResponse.json();
  return NextResponse.json(data, {
    status: fastapiResponse.status,
    headers: { "Cache-Control": "private, max-age=300, stale-while-revalidate=60" },
  });
}
