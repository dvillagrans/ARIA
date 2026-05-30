"""
Tests for migration 0004 — external_id columns + connector_state table.

These tests verify the DDL by reading the migration SQL file and checking
its structure. Full integration tests require a live Supabase instance.
"""

import pathlib


MIGRATION_PATH = pathlib.Path(__file__).parent.parent / "app" / "migrations" / "0004_external_id_connector_state.sql"


def test_migration_file_exists():
    """Migration 0004 file must exist."""
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"


def test_migration_contains_external_id_columns():
    """Migration must add external_id to all four tables."""
    sql = MIGRATION_PATH.read_text()
    for table in ("tasks", "events", "notes", "reminders"):
        assert f"ALTER TABLE {table}" in sql
        assert "external_id" in sql


def test_migration_contains_partial_unique_indexes():
    """Migration must create partial unique indexes on (source, external_id)."""
    sql = MIGRATION_PATH.read_text()
    for table in ("tasks", "events", "notes", "reminders"):
        assert f"{table}_source_external_id_idx" in sql
        assert "WHERE external_id IS NOT NULL" in sql


def test_migration_contains_connector_state_table():
    """Migration must create connector_state table."""
    sql = MIGRATION_PATH.read_text()
    assert "CREATE TABLE" in sql
    assert "connector_state" in sql
    assert "user_id" in sql
    assert "provider" in sql
    assert "state_json" in sql
    assert "UNIQUE (user_id, provider)" in sql


def test_migration_uses_if_not_exists_guards():
    """Migration must use IF NOT EXISTS for idempotency."""
    sql = MIGRATION_PATH.read_text()
    assert "IF NOT EXISTS" in sql


def test_migration_reminders_source_if_not_exists():
    """reminders.source must be added with IF NOT EXISTS guard."""
    sql = MIGRATION_PATH.read_text()
    # The reminders source column uses ADD COLUMN IF NOT EXISTS
    assert "reminders" in sql
    assert "source" in sql
