"""Tests for PulseStore — append-only measurement persistence.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §Append-only
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apoch.core.exceptions import StorageError
from apoch.modules.pulse.models import MeasurementInput, WorkUnitFilter
from apoch.modules.pulse.storage import PulseStore

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def sqlite_store() -> PulseStore:
    """Create a PulseStore backed by an in-memory SQLite database."""
    conn = sqlite3.connect(":memory:")
    store = PulseStore(conn)
    store.init_schema()
    return store


_FIELDS = dict(
    session_id="s1",
    model="claude-4",
    tokens_input=100,
    tokens_output=50,
    wall_clock_s=30.0,
)


class TestSave:
    """PulseStore.save() — append-only write."""

    def test_save_returns_work_unit(self) -> None:
        """save() MUST return a populated WorkUnit."""
        store = PulseStore()
        unit = store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert unit.id == "wu-1"
        assert unit.session_id == "s1"
        assert unit.model == "claude-4"
        assert unit.tokens_input == 100
        assert unit.tokens_output == 50
        assert unit.wall_clock_s == 30.0
        assert unit.created_at != ""

    def test_save_with_cost(self) -> None:
        """save() MUST preserve optional cost."""
        store = PulseStore()
        unit = store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.015"),
        ))
        assert unit.cost == Decimal("0.015")

    def test_save_raises_on_duplicate(self) -> None:
        """save() MUST reject duplicate work_unit_id (append-only)."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-dup", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        with pytest.raises(StorageError, match="already exists"):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id="wu-dup", model="claude-4",
                tokens_input=200, tokens_output=100, wall_clock_s=45.0,
            ))

    def test_save_append_only_no_overwrite(self) -> None:
        """save() MUST preserve the first record (append-only immutability)."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-immutable", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        with pytest.raises(StorageError):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id="wu-immutable", model="gpt-4",
                tokens_input=999, tokens_output=999, wall_clock_s=99.0,
            ))
        # First record is still intact
        unit = store.get("wu-immutable")
        assert unit is not None
        assert unit.model == "claude-4"
        assert unit.tokens_input == 100


class TestGet:
    """PulseStore.get() — read by ID."""

    def test_get_returns_unit(self) -> None:
        """get() MUST return the stored WorkUnit."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        unit = store.get("wu-1")
        assert unit is not None
        assert unit.id == "wu-1"

    def test_get_returns_none_for_unknown(self) -> None:
        """get() MUST return None for a non-existent ID."""
        store = PulseStore()
        assert store.get("nonexistent") is None


class TestList:
    """PulseStore.list() — filtered read."""

    def test_list_empty(self) -> None:
        """list() MUST return empty list when store is empty."""
        store = PulseStore()
        assert store.list() == []

    def test_list_all(self) -> None:
        """list() MUST return all stored WorkUnits (up to default limit)."""
        store = PulseStore()
        for i in range(3):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        assert len(store.list()) == 3

    def test_list_by_session(self) -> None:
        """list() MUST filter by session_id."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s-a", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s-b", work_unit_id="wu-2", model="claude-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        result = store.list(WorkUnitFilter(session_id="s-a"))
        assert len(result) == 1
        assert result[0].session_id == "s-a"

    def test_list_by_model(self) -> None:
        """list() MUST filter by model."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="gpt-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        result = store.list(WorkUnitFilter(model="gpt-4"))
        assert len(result) == 1
        assert result[0].model == "gpt-4"

    def test_list_with_limit(self) -> None:
        """list() MUST cap results at the configured limit."""
        store = PulseStore()
        for i in range(10):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        result = store.list(WorkUnitFilter(limit=3))
        assert len(result) == 3

    def test_list_newest_first(self) -> None:
        """list() MUST return results newest first."""
        store = PulseStore()
        for i in range(3):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        result = store.list()
        timestamps = [u.created_at for u in result]
        assert timestamps == sorted(timestamps, reverse=True)


class TestCount:
    """PulseStore.count() — count matching records."""

    def test_count_zero(self) -> None:
        """count() MUST return 0 on empty store."""
        store = PulseStore()
        assert store.count() == 0

    def test_count_all(self) -> None:
        """count() MUST return total record count."""
        store = PulseStore()
        for i in range(5):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        assert store.count() == 5

    def test_count_with_filter(self) -> None:
        """count() MUST respect filter criteria."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s-a", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s-b", work_unit_id="wu-2", model="gpt-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        assert store.count(WorkUnitFilter(session_id="s-a")) == 1
        assert store.count(WorkUnitFilter(model="gpt-4")) == 1


class TestSqliteInit:
    """PulseStore with SQLite backend — schema and setup."""

    def test_accepts_connection_and_inits_schema(self) -> None:
        """PulseStore MUST accept a sqlite3.Connection and init_schema()."""
        conn = sqlite3.connect(":memory:")
        store = PulseStore(conn)
        store.init_schema()
        # Verify tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        assert "work_units" in names
        assert "schema_version" in names

    def test_schema_version_inserted(self, sqlite_store: PulseStore) -> None:
        """init_schema() MUST insert a schema_version row."""
        row = sqlite_store._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] >= 1

    def test_no_connection_uses_memory(self) -> None:
        """PulseStore() without connection MUST use in-memory dict."""
        store = PulseStore()
        assert store._conn is None
        store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))
        assert store.count() == 1


class TestSqliteSave:
    """PulseStore.save() with SQLite backend."""

    def test_save_returns_work_unit(self, sqlite_store: PulseStore) -> None:
        unit = sqlite_store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))
        assert unit.id == "wu-1"
        assert unit.session_id == "s1"
        assert unit.created_at != ""

    def test_save_with_cost(self, sqlite_store: PulseStore) -> None:
        unit = sqlite_store.save(MeasurementInput(
            work_unit_id="wu-2", cost=Decimal("0.015"), **_FIELDS,
        ))
        assert unit.cost == Decimal("0.015")

    def test_save_raises_on_duplicate(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-dup", **_FIELDS))
        with pytest.raises(StorageError, match="already exists"):
            sqlite_store.save(MeasurementInput(work_unit_id="wu-dup", **_FIELDS))

    def test_persistence_across_instances(self) -> None:
        """Measurement MUST survive closing and reopening the store (R10)."""
        conn = sqlite3.connect(":memory:")
        store1 = PulseStore(conn)
        store1.init_schema()
        store1.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))

        # Close store1, open store2 with same conn
        store2 = PulseStore(conn)
        store2.init_schema()
        unit = store2.get("wu-1")
        assert unit is not None
        assert unit.id == "wu-1"
        assert unit.model == "claude-4"

    def test_save_with_lines(self, sqlite_store: PulseStore) -> None:
        """save() MUST preserve lines_original and lines_modified in SQLite."""
        unit = sqlite_store.save(MeasurementInput(
            work_unit_id="wu-lines", **_FIELDS,
            lines_original=100, lines_modified=20,
        ))
        assert unit.lines_original == 100
        assert unit.lines_modified == 20


class TestSqliteGet:
    """PulseStore.get() with SQLite backend."""

    def test_get_returns_unit(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))
        unit = sqlite_store.get("wu-1")
        assert unit is not None
        assert unit.id == "wu-1"

    def test_get_returns_none_for_unknown(self, sqlite_store: PulseStore) -> None:
        assert sqlite_store.get("nonexistent") is None


class TestSqliteList:
    """PulseStore.list() with SQLite backend."""

    def test_list_empty(self, sqlite_store: PulseStore) -> None:
        assert sqlite_store.list() == []

    def test_list_all(self, sqlite_store: PulseStore) -> None:
        for i in range(3):
            sqlite_store.save(MeasurementInput(work_unit_id=f"wu-{i}", **_FIELDS))
        assert len(sqlite_store.list()) == 3

    def test_list_by_session(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1", session_id="s-a", model="claude-4",
                                           tokens_input=100, tokens_output=50, wall_clock_s=30.0))
        sqlite_store.save(MeasurementInput(work_unit_id="wu-2", session_id="s-b", model="claude-4",
                                           tokens_input=200, tokens_output=100, wall_clock_s=60.0))
        result = sqlite_store.list(WorkUnitFilter(session_id="s-a"))
        assert len(result) == 1
        assert result[0].session_id == "s-a"

    def test_list_by_model(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1",
                                           session_id="s1", model="claude-4",
                                           tokens_input=100, tokens_output=50, wall_clock_s=30.0))
        sqlite_store.save(MeasurementInput(work_unit_id="wu-2",
                                           session_id="s1", model="gpt-4",
                                           tokens_input=200, tokens_output=100, wall_clock_s=60.0))
        result = sqlite_store.list(WorkUnitFilter(model="gpt-4"))
        assert len(result) == 1
        assert result[0].model == "gpt-4"

    def test_list_with_filter_since(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))
        # Get a timestamp after the save
        import time
        time.sleep(0.01)
        future = datetime.now(UTC).isoformat()
        result = sqlite_store.list(WorkUnitFilter(since=future))
        assert len(result) == 0

    def test_list_by_until(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))
        past = "2020-01-01T00:00:00"
        result = sqlite_store.list(WorkUnitFilter(until=past))
        assert len(result) == 0

    def test_list_with_limit(self, sqlite_store: PulseStore) -> None:
        for i in range(5):
            sqlite_store.save(MeasurementInput(work_unit_id=f"wu-{i}", **_FIELDS))
        result = sqlite_store.list(WorkUnitFilter(limit=3))
        assert len(result) == 3

    def test_list_newest_first(self, sqlite_store: PulseStore) -> None:
        for i in range(3):
            sqlite_store.save(MeasurementInput(work_unit_id=f"wu-{i}", **_FIELDS))
        result = sqlite_store.list()
        timestamps = [u.created_at for u in result]
        assert timestamps == sorted(timestamps, reverse=True)


class TestSqliteCount:
    """PulseStore.count() with SQLite backend."""

    def test_count_zero(self, sqlite_store: PulseStore) -> None:
        assert sqlite_store.count() == 0

    def test_count_all(self, sqlite_store: PulseStore) -> None:
        for i in range(5):
            sqlite_store.save(MeasurementInput(work_unit_id=f"wu-{i}", **_FIELDS))
        assert sqlite_store.count() == 5

    def test_count_with_filter(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-1", session_id="s-a", model="claude-4",
                                           tokens_input=100, tokens_output=50, wall_clock_s=30.0))
        sqlite_store.save(MeasurementInput(work_unit_id="wu-2", session_id="s-b", model="gpt-4",
                                           tokens_input=200, tokens_output=100, wall_clock_s=60.0))
        assert sqlite_store.count(WorkUnitFilter(session_id="s-a")) == 1
        assert sqlite_store.count(WorkUnitFilter(model="gpt-4")) == 1


class TestSqliteErrorWrapping:
    """SQLite errors MUST be wrapped in StorageError."""

    def test_error_on_closed_connection(self, sqlite_store: PulseStore) -> None:
        sqlite_store._conn.close()
        with pytest.raises(StorageError):
            sqlite_store.save(MeasurementInput(work_unit_id="wu-1", **_FIELDS))

    def test_error_on_duplicate_id_message(self, sqlite_store: PulseStore) -> None:
        sqlite_store.save(MeasurementInput(work_unit_id="wu-dup", **_FIELDS))
        with pytest.raises(StorageError, match="already exists"):
            sqlite_store.save(MeasurementInput(work_unit_id="wu-dup", **_FIELDS))


class TestNoAnalysisMethods:
    """PulseStore MUST NOT expose analysis methods."""

    def test_no_trend_method(self) -> None:
        """PulseStore MUST NOT have a trend/analyze method (Analysis owns this)."""
        store = PulseStore()
        assert not hasattr(store, "trend")
        assert not hasattr(store, "analyze")
        assert not hasattr(store, "rework")
        assert not hasattr(store, "aggregate")
