# ADR-04: Briefing invalidation is awaited inline, not fire-and-forget

Referenced as `ADR-4` in `backend/app/services/briefing_service.py`,
`backend/app/routes/chat.py`, and
`backend/tests/routes/test_chat_briefing_invalidation.py`.

## Context

Capturing a record must invalidate the cached daily briefing. Doing this
fire-and-forget leaves a window where the cache is stale.

## Decision

`briefing_service.invalidate()` is `await`ed inline in `chat.py`,
synchronously, right after `record_writer.write()`; invalidation is
non-fatal on error.

## Reason

The cache is guaranteed to be marked invalid (or the error observed) before
the capture request returns.
