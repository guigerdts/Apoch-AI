"""Append-only measurement store for the Pulse productivity-intelligence module.

Design: Pulse — Engineering Productivity Intelligence §Append-only
Spec: pulse-productivity-intelligence §R1–R11
"""

from __future__ import annotations

from datetime import UTC, datetime

from apoch.core.exceptions import StorageError
from apoch.modules.pulse.models import (
    MeasurementInput,
    WorkUnit,
    WorkUnitFilter,
)


class PulseStore:
    """Append-only, backend-agnostic measurement store.

    Stores :class:`WorkUnit` records in memory (v1).  The public API
    (``save``, ``get``, ``list``, ``count``) is designed as a stable
    contract — a future backend implementation (e.g. SQLite) can replace
    the internal storage without changing callers.

    Responsibilities (exclusive):
    - Persist new measurements (append-only).
    - Retrieve stored measurements by ID or filter.

    NOT responsible for: analysis, aggregation, trends, rework,
    optimisation, or recommendations.  Those belong to Analysis,
    Optimizer, and Oracle (Design §SRP).
    """

    def __init__(self) -> None:
        self._work_units: dict[str, WorkUnit] = {}

    # ------------------------------------------------------------------
    # Write (append-only)
    # ------------------------------------------------------------------

    def save(self, input: MeasurementInput) -> WorkUnit:
        """Record a new measurement and return the created :class:`WorkUnit`.

        Raises :exc:`StorageError` if a WorkUnit with the same ID
        already exists (duplicate detection).
        """
        unit_id = input.work_unit_id
        if unit_id in self._work_units:
            raise StorageError(
                f"WorkUnit '{unit_id}' already exists — append-only store "
                f"does not support overwrites."
            )

        now = datetime.now(UTC)
        unit = WorkUnit(
            id=unit_id,
            session_id=input.session_id,
            model=input.model,
            tokens_input=input.tokens_input,
            tokens_output=input.tokens_output,
            wall_clock_s=input.wall_clock_s,
            cost=input.cost,
            created_at=now.isoformat(),
        )
        self._work_units[unit_id] = unit
        return unit

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, work_unit_id: str) -> WorkUnit | None:
        """Retrieve a WorkUnit by its ID, or ``None`` if not found."""
        return self._work_units.get(work_unit_id)

    def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:
        """Return WorkUnits matching *filter*, newest first.

        All filter fields are optional.  Results are capped at
        ``filter.limit`` (default 100).  Pass ``None`` to return
        all records (up to default limit) with no filtering.
        """
        f = filter or WorkUnitFilter()
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

        # Newest first
        results.sort(key=lambda u: u.created_at, reverse=True)
        return results[: f.limit]

    def count(self, filter: WorkUnitFilter | None = None) -> int:
        """Return the number of WorkUnits matching *filter*."""
        return len(self.list(filter))
