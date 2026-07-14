"""Append-only measurement store for the Pulse productivity-intelligence module.

Design: Pulse — Engineering Productivity Intelligence §Append-only
Spec: pulse-productivity-intelligence §R1–R11
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from apoch.core.exceptions import StorageError
from apoch.modules.pulse.models import (
    MeasurementInput,
    WorkUnit,
    WorkUnitFilter,
)

# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _row_to_work_unit(row: sqlite3.Row) -> WorkUnit:
    """Convert a SQLite row to a WorkUnit, handling type conversions."""
    return WorkUnit(
        id=row["id"],
        session_id=row["session_id"],
        model=row["model"],
        tokens_input=row["tokens_input"],
        tokens_output=row["tokens_output"],
        wall_clock_s=row["wall_clock_s"],
        cost=Decimal(row["cost"]) if row["cost"] is not None else None,
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        lines_original=row["lines_original"],
        lines_modified=row["lines_modified"],
    )


def _build_where_clause(
    filter: WorkUnitFilter | None,
) -> tuple[str, list]:
    """Build a parameterised WHERE clause and parameter list from a filter."""
    f = filter or WorkUnitFilter()
    clauses: list[str] = []
    params: list = []

    if f.session_id is not None:
        clauses.append("session_id = ?")
        params.append(f.session_id)
    if f.model is not None:
        clauses.append("model = ?")
        params.append(f.model)
    if f.since is not None:
        clauses.append("created_at >= ?")
        params.append(f.since)
    if f.until is not None:
        clauses.append("created_at <= ?")
        params.append(f.until)

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


# -----------------------------------------------------------------------
# PulseStore
# -----------------------------------------------------------------------


class PulseStore:
    """Append-only, backend-agnostic measurement store.

    Stores :class:`WorkUnit` records either in memory (dict) or in a
    SQLite database.  The public API (``save``, ``get``, ``list``,
    ``count``) is backend-agnostic — callers never need to know which
    backend is active.

    Pass an ``sqlite3.Connection`` to use SQLite.  Without one, the
    store falls back to an in-memory ``dict`` for backward compatibility
    with tests and simple use cases.

    Responsibilities (exclusive):
    - Persist new measurements (append-only).
    - Retrieve stored measurements by ID or filter.

    NOT responsible for: analysis, aggregation, trends, rework,
    optimisation, or recommendations.  Those belong to Analysis,
    Optimizer, and Oracle (Design §SRP).
    """

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self._conn: sqlite3.Connection | None = conn
        self._work_units: dict[str, WorkUnit] = {}

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """Create SQLite tables if they do not exist.

        Safe to call multiple times (idempotent).
        Raises :exc:`StorageError` on SQLite errors.
        """
        if self._conn is None:
            return  # In-memory mode — no schema needed

        try:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS work_units (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_input INTEGER NOT NULL,
                    tokens_output INTEGER NOT NULL,
                    wall_clock_s REAL NOT NULL,
                    cost TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    lines_original INTEGER NOT NULL DEFAULT 0,
                    lines_modified INTEGER NOT NULL DEFAULT 0
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at) "
                "VALUES (?, ?)",
                (1, datetime.now(UTC).isoformat()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to initialise schema: {exc}") from exc

    # ------------------------------------------------------------------
    # Write (append-only)
    # ------------------------------------------------------------------

    def save(self, input: MeasurementInput) -> WorkUnit:
        """Record a new measurement and return the created :class:`WorkUnit`.

        Raises :exc:`StorageError` if a WorkUnit with the same ID
        already exists (duplicate detection) or on SQLite errors.
        """
        now = datetime.now(UTC)
        unit = WorkUnit(
            id=input.work_unit_id,
            session_id=input.session_id,
            model=input.model,
            tokens_input=input.tokens_input,
            tokens_output=input.tokens_output,
            wall_clock_s=input.wall_clock_s,
            cost=input.cost,
            created_at=now.isoformat(),
            lines_original=input.lines_original,
            lines_modified=input.lines_modified,
        )

        if self._conn is not None:
            try:
                self._conn.execute(
                    """INSERT INTO work_units
                       (id, session_id, model, tokens_input, tokens_output,
                        wall_clock_s, cost, created_at, completed_at,
                        lines_original, lines_modified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        unit.id,
                        unit.session_id,
                        unit.model,
                        unit.tokens_input,
                        unit.tokens_output,
                        unit.wall_clock_s,
                        str(unit.cost) if unit.cost is not None else None,
                        unit.created_at,
                        unit.completed_at,
                        unit.lines_original,
                        unit.lines_modified,
                    ),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise StorageError(
                    f"WorkUnit '{unit.id}' already exists — append-only "
                    f"store does not support overwrites."
                ) from exc
            except sqlite3.Error as exc:
                raise StorageError(
                    f"Failed to save WorkUnit '{unit.id}': {exc}"
                ) from exc
        else:
            # In-memory mode
            if unit.id in self._work_units:
                raise StorageError(
                    f"WorkUnit '{unit.id}' already exists — append-only store "
                    f"does not support overwrites."
                )
            self._work_units[unit.id] = unit

        return unit

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, work_unit_id: str) -> WorkUnit | None:
        """Retrieve a WorkUnit by its ID, or ``None`` if not found."""
        if self._conn is not None:
            try:
                self._conn.row_factory = sqlite3.Row
                cursor = self._conn.execute(
                    "SELECT * FROM work_units WHERE id = ?",
                    (work_unit_id,),
                )
                row = cursor.fetchone()
                return _row_to_work_unit(row) if row else None
            except sqlite3.Error as exc:
                raise StorageError(
                    f"Failed to get WorkUnit '{work_unit_id}': {exc}"
                ) from exc
        return self._work_units.get(work_unit_id)

    def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:
        """Return WorkUnits matching *filter*, newest first.

        All filter fields are optional.  Results are capped at
        ``filter.limit`` (default 100).  Pass ``None`` to return
        all records (up to default limit) with no filtering.
        """
        f = filter or WorkUnitFilter()

        if self._conn is not None:
            try:
                self._conn.row_factory = sqlite3.Row
                where, params = _build_where_clause(filter)
                cursor = self._conn.execute(
                    f"SELECT * FROM work_units WHERE {where} "
                    "ORDER BY created_at DESC LIMIT ?",
                    [*params, f.limit],
                )
                return [_row_to_work_unit(row) for row in cursor.fetchall()]
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to list WorkUnits: {exc}") from exc

        # In-memory mode
        results: list[WorkUnit] = []
        for unit in self._work_units.values():
            if f.session_id is not None and unit.session_id != f.session_id:
                continue
            if f.model is not None and unit.model != f.model:
                continue
            if f.since is not None and unit.created_at < f.since:
                continue
            if f.until is not None and unit.created_at > f.until:
                continue
            results.append(unit)

        results.sort(key=lambda u: u.created_at, reverse=True)
        return results[: f.limit]

    def count(self, filter: WorkUnitFilter | None = None) -> int:
        """Return the number of WorkUnits matching *filter*."""
        if self._conn is not None:
            try:
                where, params = _build_where_clause(filter)
                cursor = self._conn.execute(
                    f"SELECT COUNT(*) FROM work_units WHERE {where}",
                    params,
                )
                row = cursor.fetchone()
                return row[0] if row else 0
            except sqlite3.Error as exc:
                raise StorageError(f"Failed to count WorkUnits: {exc}") from exc
        return len(self.list(filter))
