/**
 * POST /api/events/sync — proxy to FastAPI POST /events/sync.
 *
 * Imports events from Google Calendar to ARIA.
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function POST(): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const fastapiResponse = await fetch(
      `${FASTAPI_BASE_URL}/events/sync?user_id=${user.id}`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    const data = await fastapiResponse.json();
    return NextResponse.json(data, { status: fastapiResponse.status });
  } catch (err) {
    console.error("[api/events/sync] FastAPI unreachable:", err);
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
