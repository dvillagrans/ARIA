# ADR-01: Supabase async clients are created per-request

Referenced as `ADR-01` in `backend/app/core/supabase_client.py`,
`backend/app/core/deps.py`, and `backend/app/routes/chat.py`.

## Context

The backend needs Supabase access for user-scoped operations. A module-level
singleton client would share connection state across requests.

## Decision

Applications settings are cached via `lru_cache`, but Supabase
`AsyncClient` instances are created per-request through FastAPI's
`Depends` (`create_async_client()` called per-request, not a singleton).

## Reason

Each request gets a fresh client; no shared mutable client state across
requests.
