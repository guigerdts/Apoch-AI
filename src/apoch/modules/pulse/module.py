"""PulseModule — engineering productivity intelligence orchestrator.

Design: Pulse — Engineering Productivity Intelligence §Data Flow
Spec: pulse-productivity-intelligence §R1–R11
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.pulse.analysis import Analysis, ProductivitySummary
from apoch.modules.pulse.models import MeasurementInput, TrendPoint, WorkUnit, WorkUnitFilter
from apoch.modules.pulse.storage import PulseStore

log = logging.getLogger(__name__)


class PulseModule(Module):
    """Pulse — engineering productivity measurement module.

    Receives :class:`MeasurementInput`, validates invariants, persists
    via :class:`PulseStore`, and exposes the module's public API.

    Responsibilities (orchestration only):
    - Accept measurement data.
    - Delegate to PulseStore for persistence.
    - Expose query API.

    NOT responsible for: trends, rework, aggregation, optimisation,
    or recommendations.  Those belong to Analysis, Optimizer, and
    Oracle (Design §SRP).
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._store: PulseStore | None = None

    # ------------------------------------------------------------------
    # Idempotent lifecycle (Chronicle pattern)
    # ------------------------------------------------------------------

    def _pre_stop(self) -> None:
        """Allow idempotent ``stop()`` — no-op if already STOPPED."""
        if self._state == ModuleState.STOPPED:
            return
        super()._pre_stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, context: Context) -> None:  # noqa: ARG002
        """Initialise PulseStore and prepare for measurement ingestion."""
        self._store = PulseStore()
        log.info("Pulse started — ready for measurement ingestion")

    async def stop(self) -> None:
        """Tear down PulseStore.  Idempotent — safe to call multiple times."""
        self._store = None

    async def shutdown(self) -> None:
        """Final cleanup.  No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Public API (measurement orchestration only)
    # ------------------------------------------------------------------

    def record(self, input: MeasurementInput) -> WorkUnit:
        """Accept a measurement and persist it.

        Validates invariants and delegates storage to PulseStore.
        Returns the created :class:`WorkUnit`.
        """
        return self._store.save(input)

    def get(self, work_unit_id: str) -> WorkUnit | None:
        """Retrieve a WorkUnit by its ID."""
        return self._store.get(work_unit_id)

    def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:
        """Query WorkUnits matching *filter*."""
        return self._store.list(filter)

    def count(self, filter: WorkUnitFilter | None = None) -> int:
        """Count WorkUnits matching *filter*."""
        return self._store.count(filter)

    # ------------------------------------------------------------------
    # Analysis (read-only, delegates to Analysis class)
    # ------------------------------------------------------------------

    def productivity_summary(self) -> ProductivitySummary:
        """Aggregate productivity metrics from stored measurements.

        Read-only — never mutates stored data.
        """
        return Analysis.summary(self._store.list())

    def trend(self, period_days: int = 1) -> list[TrendPoint]:
        """Productivity trend grouped by *period_days* windows."""
        return Analysis.trend(self._store.list(), period_days)

    def rework_rate(self) -> float:
        """Token-based rework proxy (R5).  Returns ``0.0`` for v1
        when diff metadata is unavailable."""
        return Analysis.rework_rate(self._store.list())

    # ------------------------------------------------------------------
    # Cross-module services (duck-typed)
    # ------------------------------------------------------------------

    @property
    def services(self) -> dict[str, Callable]:
        """Publish the measurement query API as a cross-module service.

        Published contract:
            key:       ``"pulse.measurements"``
            signature: ``(filter: WorkUnitFilter | None = None) -> list[WorkUnit]``
            optional:  Yes — Optimizer/Oracle degrade gracefully if absent.

        Design: Pulse — Engineering Productivity Intelligence §Interfaces / Contracts
        """
        return {"pulse.measurements": self.list}
