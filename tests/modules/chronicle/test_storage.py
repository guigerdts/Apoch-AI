"""Tests for SqliteEventStore — schema, record, query, prune, stats.

Spec: module-chronicle §Requirements
Design: PR3A — Chronicle Foundation §Testing Strategy
"""

from __future__ import annotations

import sqlite3

import pytest

from apoch.modules.chronicle.models import ActivityEvent, EventFilter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Provide an isolated SQLite database ``sqlite3.Connection``."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(str(path))
    yield conn
    conn.close()


def _store(conn: sqlite3.Connection):
    """Helper to build a SqliteEventStore from a connection."""
    from apoch.modules.chronicle.storage import SqliteEventStore

    return SqliteEventStore(conn)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchemaInit:
    """Schema initialisation creates tables and enables WAL mode."""

    def test_events_table_created(self, db):
        """``init_schema()`` creates the ``events`` table with expected columns."""
        store = _store(db)
        store.init_schema()

        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cursor.fetchone() is not None

    def test_schema_version_table_created(self, db):
        """``init_schema()`` creates the ``schema_version`` table."""
        store = _store(db)
        store.init_schema()

        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        assert cursor.fetchone() is not None

    def test_wal_mode_enabled(self, db):
        """``init_schema()`` sets journal mode to WAL."""
        store = _store(db)
        store.init_schema()

        cursor = db.execute("PRAGMA journal_mode")
        row = cursor.fetchone()
        assert row is not None
        assert row[0].lower() == "wal"

    def test_events_table_has_expected_columns(self, db):
        """The events table has id, timestamp, type, source, severity, payload columns."""
        store = _store(db)
        store.init_schema()

        cursor = db.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "id" in columns
        assert "timestamp" in columns
        assert "type" in columns
        assert "source" in columns
        assert "severity" in columns
        assert "payload" in columns


# ---------------------------------------------------------------------------
# Record & Query
# ---------------------------------------------------------------------------


class TestRecordAndQuery:
    """Round-trip record + query preserves all event fields."""

    @pytest.fixture
    def store(self, db):
        s = _store(db)
        s.init_schema()
        return s

    def _make_event(self, **overrides: object) -> ActivityEvent:
        fields = {
            "id": "abc123",
            "timestamp": "2026-07-13T12:00:00.000000+00:00",
            "type": "lifecycle",
            "source": "test",
            "severity": "info",
            "payload": {"key": "value"},
        }
        fields.update(overrides)
        return ActivityEvent(**fields)

    def test_record_and_query_all_fields_preserved(self, store):
        """Recording an event and querying returns identical data."""
        event = self._make_event()
        store.record(event)

        results = store.query(EventFilter())
        assert len(results) == 1
        stored = results[0]

        assert stored.id == event.id
        assert stored.timestamp == event.timestamp
        assert stored.type == event.type
        assert stored.source == event.source
        assert stored.severity == event.severity
        assert stored.payload == event.payload

    def test_record_payload_with_schema_key(self, store):
        """Payload with an optional 'schema' key survives round-trip."""
        payload = {"schema": "my_schema", "value": 42}
        event = self._make_event(payload=payload)
        store.record(event)

        results = store.query(EventFilter())
        assert len(results) == 1
        assert results[0].payload == payload

    def test_query_by_type(self, store):
        """Query filtered by type returns only matching events."""
        store.record(self._make_event(id="1", type="lifecycle"))
        store.record(self._make_event(id="2", type="tool_invocation"))
        store.record(self._make_event(id="3", type="lifecycle"))

        results = store.query(EventFilter(type="lifecycle"))
        assert len(results) == 2
        assert all(e.type == "lifecycle" for e in results)

    def test_query_by_source(self, store):
        """Query filtered by source returns only matching events."""
        store.record(self._make_event(id="1", source="module_a"))
        store.record(self._make_event(id="2", source="module_b"))
        store.record(self._make_event(id="3", source="module_a"))

        results = store.query(EventFilter(source="module_b"))
        assert len(results) == 1
        assert results[0].id == "2"

    def test_query_by_severity(self, store):
        """Query filtered by severity returns only matching events."""
        store.record(self._make_event(id="1", severity="info"))
        store.record(self._make_event(id="2", severity="error"))
        store.record(self._make_event(id="3", severity="info"))

        results = store.query(EventFilter(severity="error"))
        assert len(results) == 1
        assert results[0].id == "2"

    def test_query_with_time_range(self, store):
        """Query with since/until returns only events within range."""
        store.record(self._make_event(id="1", timestamp="2026-07-10T00:00:00.000000+00:00"))
        store.record(self._make_event(id="2", timestamp="2026-07-11T12:00:00.000000+00:00"))
        store.record(self._make_event(id="3", timestamp="2026-07-12T00:00:00.000000+00:00"))

        results = store.query(
            EventFilter(
                since="2026-07-11T00:00:00.000000+00:00",
                until="2026-07-13T00:00:00.000000+00:00",
            )
        )
        assert len(results) == 2
        assert {e.id for e in results} == {"2", "3"}

    def test_query_with_limit(self, store):
        """Query with limit returns at most that many results (most recent)."""
        for i in range(10):
            ts = f"2026-07-13T12:00:0{i}.000000+00:00"
            store.record(self._make_event(id=str(i), timestamp=ts))

        results = store.query(EventFilter(limit=3))
        assert len(results) == 3
        # Most recent (descending timestamp): ids 9, 8, 7
        assert [r.id for r in results] == ["9", "8", "7"]

    def test_query_with_combined_filters(self, store):
        """Multiple filters applied together return correct intersection."""
        store.record(self._make_event(id="1", type="lifecycle", source="mod_a", severity="info"))
        store.record(self._make_event(id="2", type="error", source="mod_a", severity="error"))
        store.record(self._make_event(id="3", type="lifecycle", source="mod_b", severity="info"))

        results = store.query(EventFilter(type="lifecycle", source="mod_a"))
        assert len(results) == 1
        assert results[0].id == "1"

    def test_query_with_no_matches_returns_empty_list(self, store):
        """Query that matches zero events returns empty list, not None."""
        store.record(self._make_event(type="lifecycle"))

        results = store.query(EventFilter(type="nonexistent"))
        assert results == []


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------


class TestPrune:
    """Event pruning removes old events only."""

    @pytest.fixture
    def store(self, db):
        s = _store(db)
        s.init_schema()
        return s

    def test_prune_removes_old_events(self, store):
        """Events older than cutoff are deleted; newer ones remain."""
        store.record(
            ActivityEvent(
                id="old",
                timestamp="2026-01-01T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="new",
                timestamp="2026-07-01T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )

        deleted = store.prune("2026-06-01T00:00:00.000000+00:00")
        assert deleted == 1

        remaining = store.query(EventFilter())
        assert len(remaining) == 1
        assert remaining[0].id == "new"

    def test_prune_with_no_old_events_is_noop(self, store):
        """Pruning with a cutoff before all events deletes nothing."""
        store.record(
            ActivityEvent(
                id="a",
                timestamp="2026-07-01T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="b",
                timestamp="2026-07-02T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )

        deleted = store.prune("2026-01-01T00:00:00.000000+00:00")
        assert deleted == 0

        remaining = store.query(EventFilter())
        assert len(remaining) == 2

    def test_prune_returns_count(self, store):
        """Prune returns the exact number of deleted rows."""
        store.record(
            ActivityEvent(
                id="x",
                timestamp="2026-01-01T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="y",
                timestamp="2026-01-02T00:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )

        deleted = store.prune("2026-06-01T00:00:00.000000+00:00")
        assert deleted == 2


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    """Aggregate statistics are accurate."""

    @pytest.fixture
    def store(self, db):
        s = _store(db)
        s.init_schema()
        return s

    def test_stats_total(self, store):
        """Stats returns correct total event count."""
        for i in range(5):
            store.record(
                ActivityEvent(
                    id=str(i),
                    timestamp=f"2026-07-13T12:00:0{i}.000000+00:00",
                    type="test",
                    source="t",
                    severity="info",
                    payload={},
                )
            )

        stats = store.stats()
        assert stats.total == 5

    def test_stats_by_type(self, store):
        """Stats breaks down counts by event type."""
        store.record(
            ActivityEvent(
                id="1",
                timestamp="2026-07-13T12:00:00.000000+00:00",
                type="lifecycle",
                source="t",
                severity="info",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="2",
                timestamp="2026-07-13T12:00:01.000000+00:00",
                type="error",
                source="t",
                severity="error",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="3",
                timestamp="2026-07-13T12:00:02.000000+00:00",
                type="lifecycle",
                source="t",
                severity="info",
                payload={},
            )
        )

        stats = store.stats()
        assert stats.by_type == {"lifecycle": 2, "error": 1}

    def test_stats_by_severity(self, store):
        """Stats breaks down counts by severity."""
        store.record(
            ActivityEvent(
                id="1",
                timestamp="2026-07-13T12:00:00.000000+00:00",
                type="t",
                source="t",
                severity="info",
                payload={},
            )
        )
        store.record(
            ActivityEvent(
                id="2",
                timestamp="2026-07-13T12:00:01.000000+00:00",
                type="t",
                source="t",
                severity="fatal",
                payload={},
            )
        )

        stats = store.stats()
        assert stats.by_severity == {"info": 1, "fatal": 1}

    def test_stats_on_empty_db(self, store):
        """Stats on an empty database returns zeros and empty dicts."""
        stats = store.stats()
        assert stats.total == 0
        assert stats.by_type == {}
        assert stats.by_severity == {}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """SqliteEventStore wraps raw sqlite3 exceptions in StorageError."""

    def test_operation_on_closed_connection_raises_storage_error(self, tmp_path):
        """Any operation on a closed connection raises StorageError, not raw sqlite3."""
        path = tmp_path / "closed.db"
        conn = sqlite3.connect(str(path))
        from apoch.core.exceptions import StorageError
        from apoch.modules.chronicle.storage import SqliteEventStore

        store = SqliteEventStore(conn)
        conn.close()

        with pytest.raises(StorageError):
            store.init_schema()

    def test_record_on_closed_connection_raises_storage_error(self, tmp_path):
        """Record on a closed connection raises StorageError."""
        path = tmp_path / "closed2.db"
        conn = sqlite3.connect(str(path))
        from apoch.core.exceptions import StorageError
        from apoch.modules.chronicle.storage import SqliteEventStore

        store = SqliteEventStore(conn)
        store.init_schema()
        conn.close()

        with pytest.raises(StorageError):
            store.record(
                ActivityEvent(
                    id="1",
                    timestamp="2026-01-01T00:00:00.000000+00:00",
                    type="t",
                    source="t",
                    severity="info",
                    payload={},
                )
            )
