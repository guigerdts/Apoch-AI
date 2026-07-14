"""PulseModule — engineering productivity intelligence orchestrator.

Design: Pulse — Engineering Productivity Intelligence §Data Flow
Spec: pulse-productivity-intelligence §R1–R11
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from decimal import Decimal

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
        self._db_conn: sqlite3.Connection | None = None
        self._pricing: dict[str, Decimal] = config.get("model_pricing", {})

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
        """Initialise PulseStore and prepare for measurement ingestion.

        When ``config["pulse_db_path"]`` is set, opens a SQLite connection
        for persistent storage.  Otherwise falls back to in-memory dict
        (backward compatible for testing).
        """
        db_path = self._config.get("pulse_db_path")
        if db_path:
            self._db_conn = sqlite3.connect(str(db_path))
            self._store = PulseStore(self._db_conn)
            self._store.init_schema()
            log.info("Pulse started with SQLite at %s", db_path)
        else:
            self._store = PulseStore()
            log.info("Pulse started — in-memory mode (no pulse_db_path configured)")

    async def stop(self) -> None:
        """Tear down PulseStore.  Idempotent — safe to call multiple times."""
        if self._db_conn is not None:
            self._db_conn.close()
            self._db_conn = None
        self._store = None

    async def shutdown(self) -> None:
        """Final cleanup.  No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Public API (measurement orchestration only)
    # ------------------------------------------------------------------

    def record(self, input: MeasurementInput) -> WorkUnit:
        """Accept a measurement and persist it.

        When ``input.cost`` is ``None``, tries to compute cost from the
        configured ``model_pricing`` dict.  If the model has no configured
        price, logs a warning and keeps ``cost=None``.

        Returns the created :class:`WorkUnit`.
        """
        cost = input.cost
        if cost is None:
            price = self._pricing.get(input.model)
            if price is not None:
                total_tokens = input.tokens_input + input.tokens_output
                cost = Decimal(str(total_tokens)) * price
            else:
                log.warning("No price configured for model '%s'", input.model)

        # Create a new MeasurementInput with the computed cost to pass to storage
        record_input = MeasurementInput(
            session_id=input.session_id,
            work_unit_id=input.work_unit_id,
            model=input.model,
            tokens_input=input.tokens_input,
            tokens_output=input.tokens_output,
            wall_clock_s=input.wall_clock_s,
            cost=cost,
            lines_original=input.lines_original,
            lines_modified=input.lines_modified,
        )
        return self._store.save(record_input)

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

    def rework_rate(self, window_days: int = 30) -> float:
        """Compute rework rate from stored measurements.

        Uses line-based calculation when available (any WorkUnit has
        ``lines_original > 0``), falling back to a token-based proxy.

        *window_days* controls the time window for line-based calculation
        (units completed beyond the window are excluded).

        Returns a float between 0.0 and 1.0.
        """
        rate, _ = Analysis.rework_rate(self._store.list(), window_days=window_days)
        return rate

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
