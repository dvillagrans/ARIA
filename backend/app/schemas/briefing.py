"""
Briefing response schema.

Returned by GET /briefing. The `cached` and `stale` flags indicate the
3-state cache outcome (fresh / stale / generated).
"""

from datetime import date, datetime

from pydantic import BaseModel


class BriefingResponse(BaseModel):
    content: str
    cached: bool
    stale: bool
    date: date
    generated_at: datetime
