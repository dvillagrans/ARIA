"""
TDD tests — CaptureIntent path calls briefing_service.invalidate().

Spec: Modified Capability — CaptureIntent Triggers Briefing Invalidation
Design ADR-4: await briefing_service.invalidate() inline after record_writer.write()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _make_mock_db_for_chat():
    """
    Build a mock db that satisfies the chat orchestrator's DB calls:
    - projects select query
    - tasks insert (record_writer)
    - conversations insert x2 (conversation_service.save)
    - briefings update (briefing_service.invalidate)
    """
    db = MagicMock()
    _id = str(uuid4())

    generic_execute = AsyncMock(return_value=MagicMock(data=[]))

    # Projects query result
    projects_execute = AsyncMock(
        return_value=MagicMock(
            data=[{"id": str(uuid4()), "name": "Personal", "is_active": True}]
        )
    )

    # Task insert result
    task_execute = AsyncMock(
        return_value=MagicMock(data=[{"id": _id, "title": "Test task"}])
    )
    task_insert = MagicMock(return_value=MagicMock(execute=task_execute))

    # Conversation insert result
    conv_execute = AsyncMock(return_value=MagicMock(data=[{"id": str(uuid4())}]))
    conv_insert = MagicMock(return_value=MagicMock(execute=conv_execute))

    # Briefings update (invalidate)
    update_eq2 = MagicMock(return_value=MagicMock(execute=generic_execute))
    update_eq1 = MagicMock(return_value=MagicMock(eq=update_eq2))
    update_call = MagicMock(return_value=MagicMock(eq=update_eq1))

    def table_router(table_name: str):
        mock = MagicMock()
        if table_name == "projects":
            mock.select = MagicMock(
                return_value=MagicMock(
                    eq=MagicMock(
                        return_value=MagicMock(
                            eq=MagicMock(
                                return_value=MagicMock(execute=projects_execute)
                            )
                        )
                    )
                )
            )
        elif table_name == "tasks":
            mock.insert = task_insert
        elif table_name == "conversations":
            mock.insert = conv_insert
        elif table_name == "briefings":
            mock.update = update_call
        else:
            mock.insert = MagicMock(return_value=MagicMock(execute=generic_execute))
        return mock

    db.table = MagicMock(side_effect=table_router)
    return db


class TestChatBriefingInvalidation:
    """Tests that CaptureIntent branch in POST /chat calls briefing_service.invalidate()."""

    def test_capture_triggers_briefing_invalidation(self):
        """
        Successful capture → briefing_service.invalidate called once.

        Uses FastAPI dependency_overrides to inject the mock db without
        making real Supabase connections.
        """
        import uuid
        from app.main import app
        from app.core.deps import get_async_supabase, get_llm, get_embedder
        from app.schemas.classifier import CaptureIntent

        user_id = str(uuid4())
        capture_intent = CaptureIntent(
            intent="capture",
            record_type="task",
            title="Buy milk",
            energy_level="medium",
        )
        record_id = uuid.uuid4()
        mock_db = _make_mock_db_for_chat()

        mock_llm = MagicMock()
        mock_llm.reason = AsyncMock(return_value="Captured: Buy milk")

        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 1536)

        async def override_db():
            return mock_db

        async def override_llm():
            return mock_llm

        async def override_embedder():
            return mock_embedder

        app.dependency_overrides[get_async_supabase] = override_db
        app.dependency_overrides[get_llm] = override_llm
        app.dependency_overrides[get_embedder] = override_embedder

        try:
            with (
                patch(
                    "app.routes.chat.classifier_service.classify",
                    new_callable=AsyncMock,
                    return_value=capture_intent,
                ),
                patch(
                    "app.routes.chat.project_resolver.resolve",
                    new_callable=AsyncMock,
                    return_value={"id": str(uuid4()), "name": "Personal"},
                ),
                patch(
                    "app.routes.chat.record_writer.write",
                    new_callable=AsyncMock,
                    return_value=("tasks", record_id, "Buy milk"),
                ),
                patch(
                    "app.routes.chat.briefing_service.invalidate",
                    new_callable=AsyncMock,
                ) as mock_invalidate,
            ):
                with TestClient(app) as c:
                    response = c.post(
                        "/chat",
                        json={"message": "Buy milk", "user_id": user_id},
                    )

            assert response.status_code == 200
            mock_invalidate.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_async_supabase, None)
            app.dependency_overrides.pop(get_llm, None)
            app.dependency_overrides.pop(get_embedder, None)

    def test_invalidation_error_does_not_fail_capture(self):
        """
        briefing_service.invalidate raises exception → task still written, 200 returned.
        """
        import uuid
        from app.main import app
        from app.core.deps import get_async_supabase, get_llm, get_embedder
        from app.schemas.classifier import CaptureIntent

        user_id = str(uuid4())
        capture_intent = CaptureIntent(
            intent="capture",
            record_type="task",
            title="Meeting notes",
            energy_level="medium",
        )
        record_id = uuid.uuid4()
        mock_db = _make_mock_db_for_chat()

        mock_llm = MagicMock()
        mock_llm.reason = AsyncMock(return_value="Captured: Meeting notes")

        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 1536)

        async def override_db():
            return mock_db

        async def override_llm():
            return mock_llm

        async def override_embedder():
            return mock_embedder

        app.dependency_overrides[get_async_supabase] = override_db
        app.dependency_overrides[get_llm] = override_llm
        app.dependency_overrides[get_embedder] = override_embedder

        try:
            with (
                patch(
                    "app.routes.chat.classifier_service.classify",
                    new_callable=AsyncMock,
                    return_value=capture_intent,
                ),
                patch(
                    "app.routes.chat.project_resolver.resolve",
                    new_callable=AsyncMock,
                    return_value={"id": str(uuid4()), "name": "Personal"},
                ),
                patch(
                    "app.routes.chat.record_writer.write",
                    new_callable=AsyncMock,
                    return_value=("tasks", record_id, "Meeting notes"),
                ),
                patch(
                    "app.routes.chat.briefing_service.invalidate",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("DB connection lost"),
                ),
            ):
                with TestClient(app) as c:
                    response = c.post(
                        "/chat",
                        json={"message": "Meeting notes", "user_id": user_id},
                    )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_async_supabase, None)
            app.dependency_overrides.pop(get_llm, None)
            app.dependency_overrides.pop(get_embedder, None)
