/**
 * GET /api/reminders/due — proxy to FastAPI GET /reminders/due.
 *
 * Returns overdue reminders (due_at <= now AND is_done = false).
 * Used by the reminder polling hook.
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function GET(): Promise<Response> {
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
      `${FASTAPI_BASE_URL}/reminders/due?user_id=${user.id}`,
      { method: "GET", headers: { "Content-Type": "application/json" } }
    );
    const data = await fastapiResponse.json();
    return NextResponse.json(data, { status: fastapiResponse.status });
  } catch (err) {
    console.error("[api/reminders/due] FastAPI unreachable:", err);
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
