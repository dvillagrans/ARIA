# ADR-05: user_id is injected server-side

Referenced as `ADR-05` in `backend/app/schemas/chat.py` and
`frontend/app/api/chat/route.ts`.

## Context

Every chat request carries a `user_id`. Trusting the browser to send the
correct `user_id` would let any caller impersonate another user.

## Decision

The Next.js API route reads `user_id` from the Supabase session
server-side and injects it into the forwarded request; the browser never
sends `user_id` directly. FastAPI trusts it as-is (single-user system).

## Reason

A spoofed frontend cannot record data under another user's identity.
