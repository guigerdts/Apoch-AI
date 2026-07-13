"""SQLite-backed event store for the Chronicle activity-recording module.

Design: PR3A — Chronicle Foundation §Interfaces / Contracts
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from apoch.core.exceptions import StorageError
from apoch.modules.chronicle.models import ActivityEvent, EventFilter, EventStats


class SqliteEventStore:
    """SQLite-backed event store with WAL mode and microsecond precision.

    The store operates on an externally-owned ``sqlite3.Connection`` —
    it does not manage its own connection lifecycle.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Create the ``events`` and ``schema_version`` tables and enable WAL."""
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id         TEXT PRIMARY KEY,
                    timestamp  TEXT NOT NULL,
                    type       TEXT NOT NULL,
                    source     TEXT NOT NULL,
                    severity   TEXT NOT NULL,
                    payload    TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS schema_version (
                    version    INT NOT NULL,
                    applied_at TEXT NOT NULL
                );
            """)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to initialise chronicle schema: {exc}") from exc

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, event: ActivityEvent) -> None:
        """Persist an activity event."""
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO events (id, timestamp, type, source, severity, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.timestamp,
                    event.type,
                    event.source,
                    event.severity,
                    json.dumps(event.payload),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to record event: {exc}") from exc

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, event_filter: EventFilter) -> list[ActivityEvent]:
        """Retrieve events matching the given filter, newest first.

        Each filter field is optional — only the specified criteria are
        applied.  Results are capped at *limit* (default 100).
        """
        try:
            clauses: list[str] = []
            params: list[Any] = []

            if event_filter.type is not None:
                clauses.append("type = ?")
                params.append(event_filter.type)
            if event_filter.source is not None:
                clauses.append("source = ?")
                params.append(event_filter.source)
            if event_filter.severity is not None:
                clauses.append("severity = ?")
                params.append(event_filter.severity)
            if event_filter.since is not None:
                clauses.append("timestamp >= ?")
                params.append(event_filter.since)
            if event_filter.until is not None:
                clauses.append("timestamp <= ?")
                params.append(event_filter.until)

            where = ""
            if clauses:
                where = "WHERE " + " AND ".join(clauses)

            sql = (
                "SELECT id, timestamp, type, source, severity, payload "
                f"FROM events {where} ORDER BY timestamp DESC LIMIT ?"
            )
            params.append(event_filter.limit)

            rows = self._conn.execute(sql, params).fetchall()
            return [
                ActivityEvent(
                    id=row[0],
                    timestamp=row[1],
                    type=row[2],
                    source=row[3],
                    severity=row[4],
                    payload=json.loads(row[5]),
                )
                for row in rows
            ]
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to query events: {exc}") from exc

    # ------------------------------------------------------------------
    # Prune
    # ------------------------------------------------------------------

    def prune(self, before: str) -> int:
        """Delete events older than *before* (ISO 8601).

        Returns the number of deleted rows.
        """
        try:
            cursor = self._conn.execute("DELETE FROM events WHERE timestamp < ?", (before,))
            self._conn.commit()
            return cursor.rowcount
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to prune events: {exc}") from exc

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> EventStats:
        """Return aggregate statistics over all recorded events."""
        try:
            total = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

            type_rows = self._conn.execute(
                "SELECT type, COUNT(*) AS cnt FROM events GROUP BY type"
            ).fetchall()
            by_type = {row[0]: row[1] for row in type_rows}

            severity_rows = self._conn.execute(
                "SELECT severity, COUNT(*) AS cnt FROM events GROUP BY severity"
            ).fetchall()
            by_severity = {row[0]: row[1] for row in severity_rows}

            return EventStats(total=total, by_type=by_type, by_severity=by_severity)
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to compute event stats: {exc}") from exc
