/**
 * POST /api/chat — server-side route handler.
 *
 * ADR-05: Reads user_id from the Supabase session server-side.
 * The browser never sends user_id — this handler injects it before
 * forwarding to FastAPI. Phase 1: trusts user_id as-is (no JWT verify
 * on the FastAPI side).
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request): Promise<Response> {
  // 1. Authenticate the caller via Supabase session (server-side).
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. Parse the request body (browser sends { message } or { message, project_id }).
  let body: { message: string; project_id?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.message || typeof body.message !== "string") {
    return NextResponse.json(
      { error: "message field is required" },
      { status: 400 }
    );
  }

  // 3. Forward to FastAPI with user_id injected server-side.
  let fastapiResponse: Response;
  try {
    fastapiResponse = await fetch(`${FASTAPI_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: body.message,
        user_id: user.id,
        project_id: body.project_id ?? null,
      }),
    });
  } catch (err) {
    console.error("[api/chat] FastAPI unreachable:", err);
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 503 }
    );
  }

  // 4. Return FastAPI ChatResponse as-is.
  let data: unknown;
  try {
    data = await fastapiResponse.json();
  } catch {
    console.error(
      "[api/chat] FastAPI returned non-JSON body, status:",
      fastapiResponse.status
    );
    return NextResponse.json(
      { error: "Backend error" },
      { status: fastapiResponse.status }
    );
  }
  return NextResponse.json(data, { status: fastapiResponse.status });
}
