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
    const res = await fetch(
      `${FASTAPI_BASE_URL}/connectors/sync/github/me?user_id=${user.id}`,
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[api/integrations/github/sync] Backend unreachable:", err);
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
