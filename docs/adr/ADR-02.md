# ADR-02: Providers return raw dicts; the schema layer owns typed parsing

Referenced as `ADR-02` in `backend/app/providers/deepseek.py`,
`backend/app/schemas/classifier.py`, and
`backend/app/services/classifier_service.py`.

## Context

The LLM provider returns parsed JSON from the model. Something must turn that
raw JSON into the typed `ClassifierOutput`.

## Decision

`DeepSeekProvider.classify()` returns a `dict` (raw parsed JSON).
`ClassifierOutput` is resolved via a Pydantic v2 discriminated union on the
`intent` literal field, and `classifier_service` owns that parse (including
schema-level retries). Related notes the same decision records: the
classification model is `deepseek-chat`, the reasoning model is
`deepseek-reasoner` (cited as `ADR-1` in `deepseek.py` and its tests).

## Reason

Providers stay schema-agnostic; typed routing is enforced at the schema
boundary via the discriminated union.
