# ADR-03: pg_trgm similarity for fuzzy task lookup

Referenced as `ADR-3` in `backend/app/services/context_note_service.py`,
`backend/app/services/briefing_service.py`, and
`backend/tests/services/test_context_note_service.py`.

## Context

`context_note_update` needs to find the task a follow-up message refers to
when titles do not match exactly.

## Decision

Use Postgres `pg_trgm` `similarity() > 0.3` for task title matching; the
threshold is enforced in SQL (task lookup), and `_score_task()` in the
briefing service stays a pure function (no DB), unit-testable.

## Reason

Fuzzy matching happens in the database where the data lives; scoring logic
that must not depend on the DB stays pure and testable.
