/**
 * POST /api/chat — server-side route handler.
 *
 * ADR-05: Reads user_id from the Supabase session server-side.
 * Accepts the useChat wire format: { messages: [...], project_id? }
 * Calls FastAPI and streams the confirmation_text back word-by-word.
 */

import { createClient } from "@/lib/supabase/server";

const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

export async function POST(req: Request): Promise<Response> {
  // 1. Authenticate via Supabase session.
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return new Response("Unauthorized", { status: 401 });
  }

  // 2. Parse useChat body: { messages: CoreMessage[], project_id? }
  let body: {
    messages?: Array<{ role: string; content: string }>;
    project_id?: string;
  };
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON body", { status: 400 });
  }

  const lastUserMessage = [...(body.messages ?? [])]
    .reverse()
    .find((m) => m.role === "user");

  if (!lastUserMessage?.content) {
    return new Response("No user message found", { status: 400 });
  }

  // 3. Forward to FastAPI.
  let fastapiResponse: Response;
  try {
    fastapiResponse = await fetch(`${FASTAPI_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: lastUserMessage.content,
        user_id: user.id,
        project_id: body.project_id ?? null,
      }),
    });
  } catch (err) {
    console.error("[api/chat] FastAPI unreachable:", err);
    return new Response("Backend unavailable", { status: 503 });
  }

  // 4. Parse FastAPI JSON response.
  let data: unknown;
  try {
    data = await fastapiResponse.json();
  } catch {
    console.error("[api/chat] FastAPI non-JSON, status:", fastapiResponse.status);
    return new Response("Backend error", { status: fastapiResponse.status });
  }

  if (!fastapiResponse.ok) {
    const detail =
      (data as Record<string, unknown>)?.detail ?? "Backend error";
    return new Response(String(detail), { status: fastapiResponse.status });
  }

  const text =
    ((data as Record<string, unknown>)?.confirmation_text as string) ?? "Done.";

  // 5. Stream word-by-word so the client sees a typing effect.
  //    FastAPI already computed the full response; streaming here is cosmetic
  //    but meaningfully improves perceived UX.
  const encoder = new TextEncoder();
  const tokens = text.split(/(\s+)/); // preserves whitespace between words

  const stream = new ReadableStream({
    async start(controller) {
      for (const token of tokens) {
        controller.enqueue(encoder.encode(token));
        // Only delay on non-whitespace tokens (words).
        if (token.trim()) {
          await new Promise((r) => setTimeout(r, 18));
        }
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
