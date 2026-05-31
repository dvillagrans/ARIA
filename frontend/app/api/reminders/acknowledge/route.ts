/**
 * POST /api/reminders/acknowledge — proxy to FastAPI POST /reminders/{id}/acknowledge.
 *
 * Marks a reminder as done (is_done = true).
 */

import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { reminder_id: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.reminder_id) {
    return NextResponse.json(
      { error: "reminder_id is required" },
      { status: 400 }
    );
  }

  try {
    const fastapiResponse = await fetch(
      `${FASTAPI_BASE_URL}/reminders/${body.reminder_id}/acknowledge?user_id=${user.id}`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    const data = await fastapiResponse.json();
    return NextResponse.json(data, { status: fastapiResponse.status });
  } catch (err) {
    console.error("[api/reminders/acknowledge] FastAPI unreachable:", err);
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
