"""OracleModule — recommendation engine lifecycle and service wiring.

Spec: oracle-recommendation-engine §R1, R5, R6, R8, R9, R10, Constraint B
Design: Oracle — Recommendation Engine §Lifecycle, §Service Wiring, §Chronicle Integration
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.oracle.engine import RecommendationEngine
from apoch.modules.oracle.models import Recommendation

log = logging.getLogger(__name__)


class OracleModule(Module):
    """Oracle — recommendation engine module.

    Exposes ``oracle.recommendations`` and ``oracle.status`` as
    cross-module duck-typed services.

    Responsibilities (adapter only, see Constraint B):
    - Lifecycle: start/stop/shutdown with idempotent state transitions.
    - Service wiring: discover Optimizer, Guardian/Vision, Chronicle.
    - Orchestration: fetch hypotheses → build health context → engine → record.

    NOT responsible for:
    - Recommendation logic, priority mapping, or domain rules
      (those belong exclusively in RecommendationEngine).
    - Direct import of other first-party modules (Rule 005/006).
    - Own persistence (ephemeral mode when Chronicle is absent).
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._engine: RecommendationEngine | None = None
        self._context: Context | None = None

    # ------------------------------------------------------------------
    # Idempotent lifecycle (same pattern as OptimizerModule)
    # ------------------------------------------------------------------

    def _pre_stop(self) -> None:
        """Allow idempotent ``stop()`` — no-op if already STOPPED."""
        if self._state == ModuleState.STOPPED:
            return
        super()._pre_stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, context: Context) -> None:
        """Store context and instantiate the RecommendationEngine.

        Args:
            context: Execution context with cross-module service references.
        """
        self._context = context
        self._engine = RecommendationEngine()
        log.info("Oracle started — RecommendationEngine ready")

    async def stop(self) -> None:
        """Clear context and engine references. Idempotent."""
        self._context = None
        self._engine = None

    async def shutdown(self) -> None:
        """Final cleanup. No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Cross-module services (duck-typed)
    # ------------------------------------------------------------------

    @property
    def services(self) -> dict[str, Callable]:
        """Publish the Oracle API as cross-module services.

        Published contract::

            key:       ``"oracle.recommendations"``
            signature: ``() -> list[Recommendation]``

            key:       ``"oracle.status"``
            signature: ``() -> dict``
        """
        return {
            "oracle.recommendations": self._get_recommendations,
            "oracle.status": self._get_status,
        }

    # ------------------------------------------------------------------
    # Internal: recommendation orchestration
    # ------------------------------------------------------------------

    def _get_recommendations(self) -> list[Recommendation]:
        """Fetch hypotheses, build health context, run engine, record events.

        Returns:
            Sorted list of recommendations, or ``[]`` when Optimizer is absent.
        """
        hyps = self._get_hypotheses()
        health = self._get_health()
        recs = self._engine.generate(hyps, health) if self._engine else []
        self._try_record(recs)
        return recs

    def _get_hypotheses(self) -> list[Any]:
        """Fetch hypotheses from Optimizer via sentinel pattern.

        Sentinel pattern (R6, R9):
        - No context → empty list.
        - ``optimizer.hypotheses`` service absent → empty list.
        - Service call fails → empty list.
        - Service returns ``None`` → empty list.
        """
        if self._context is None:
            return []
        try:
            measurements = self._context.services.get("optimizer.hypotheses")
        except Exception:  # noqa: BLE001
            return []
        if measurements is None:
            return []
        try:
            result = measurements()
        except Exception:  # noqa: BLE001
            return []
        return result or []

    def _get_health(self) -> dict[str, Any] | None:
        """Collect health diagnostics from Guardian/Vision (optional).

        Returns:
            Aggregated health dict, or ``None`` when no diagnostics found.
        """
        health: dict[str, Any] = {}

        # Guardian diagnostics
        try:
            diagnostics = self._context.services.get("guardian.diagnostics")  # type: ignore[union-attr]
            if diagnostics:
                health["guardian"] = diagnostics()
        except Exception:  # noqa: BLE001
            pass

        # Vision module state
        try:
            module_state = self._context.services.get("vision.module_state")  # type: ignore[union-attr]
            if module_state:
                health["vision"] = module_state()
        except Exception:  # noqa: BLE001
            pass

        return health or None

    # ------------------------------------------------------------------
    # Internal: Chronicle event writing (non-blocking)
    # ------------------------------------------------------------------

    def _try_record(self, recs: list[Recommendation]) -> None:
        """Write recommendation lifecycle events to Chronicle.

        Non-blocking try/except — Chronicle failures are logged and
        never propagate.  Absent Chronicle → silent skip (ephemeral mode).

        Args:
            recs: Recommendations to record as events.
        """
        if not recs:
            return
        try:
            record = self._context.services.get("chronicle.record")  # type: ignore[union-attr]
            if record is None:
                return
            for rec in recs:
                record({
                    "type": "recommendation_generated",
                    "payload": asdict(rec),
                })
        except Exception:  # noqa: BLE001
            log.exception("Failed to record recommendation to Chronicle")

    # ------------------------------------------------------------------
    # Internal: status
    # ------------------------------------------------------------------

    def _get_status(self) -> dict[str, Any]:
        """Return current Oracle status.

        Returns:
            A dict with ``available``, ``optimizer_connected``, and
            ``chronicle_connected``.
        """
        services_available = (
            self._context is not None and self._context.services is not None
        )
        optimizer_connected = (
            services_available
            and "optimizer.hypotheses" in self._context.services
        )
        chronicle_connected = (
            services_available
            and "chronicle.record" in self._context.services
        )
        return {
            "available": True,
            "optimizer_connected": optimizer_connected,
            "chronicle_connected": chronicle_connected,
        }


__all__ = [
    "OracleModule",
]
