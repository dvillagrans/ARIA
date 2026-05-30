"""
Project resolver service.

Maps an optional project_hint string from the classifier to one of the user's
active projects via fuzzy string matching. Never raises or returns None unless
the user has literally no projects (which should not happen after the migration).

Spec §3 / ADR-01.
"""

from __future__ import annotations

import logging

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 60.0  # rapidfuzz scores are 0–100


async def resolve(
    hint: str | None,
    projects: list[dict],
) -> dict | None:
    """
    Resolve a project_hint to an active project.

    Args:
        hint: Optional string from the classifier (e.g. "Work", "wrk").
        projects: List of active project dicts with at least 'name' and 'id'.

    Returns:
        The best-matching project dict, or the "Personal" project as fallback,
        or None if projects is empty.
    """
    if not projects:
        return None

    # Locate the Personal project for fallback use.
    personal = next((p for p in projects if p["name"] == "Personal"), None)

    if not hint:
        return personal or projects[0]

    # Compute fuzzy ratio scores (case-insensitive).
    hint_lower = hint.lower()
    best_project = None
    best_score = 0.0

    for project in projects:
        score = fuzz.ratio(hint_lower, project["name"].lower())
        if score > best_score:
            best_score = score
            best_project = project

    if best_score >= _FUZZY_THRESHOLD and best_project is not None:
        logger.debug(
            "project_resolver: matched '%s' → '%s' (score=%.1f)",
            hint,
            best_project["name"],
            best_score,
        )
        return best_project

    logger.debug(
        "project_resolver: no match for '%s' (best=%.1f < %.1f), falling back to Personal",
        hint,
        best_score,
        _FUZZY_THRESHOLD,
    )
    return personal or projects[0]
