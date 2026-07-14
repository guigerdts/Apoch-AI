"""OptimizerModule — engineering optimization intelligence orchestrator.

Spec: optimizer-engineering-optimization §R9–R12
Design: Optimizer — Engineering Optimization Intelligence §Lifecycle, §Orchestration
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.optimizer._detectors import (
    AnomalyDetector,
    BaselineGenerator,
    DegradationDetector,
    Detector,
    ModelEfficiencyDetector,
    ReworkCorrelationDetector,
    SessionPatternDetector,
)
from apoch.modules.optimizer.models import OptimizationHypothesis

log = logging.getLogger(__name__)


class OptimizerModule(Module):
    """Optimizer — engineering optimization intelligence module.

    Orchestrates all 6 detectors to produce actionable optimisation
    hypotheses from Pulse measurements.  Degrades gracefully when
    Pulse is absent (R11).

    Responsibilities (orchestration only):
    - Run all 6 detectors in a single ``_run_cycle``.
    - Isolate detector failures (one failing detector never blocks others).
    - Sort and return hypotheses in a deterministic order.

    NOT responsible for: hypothesis storage, service registration,
    entry-point wiring, or real Pulse integration.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._detectors: list[Detector] = []
        self._context: Context | None = None

    # ------------------------------------------------------------------
    # Idempotent lifecycle (Chronicle/Pulse pattern)
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
        """Register all 6 detectors and store the execution context.

        Detectors are registered in a fixed order that determines the
        sort priority of returned hypotheses.
        """
        self._context = context
        self._detectors = [
            BaselineGenerator(),
            DegradationDetector(),
            ModelEfficiencyDetector(),
            AnomalyDetector(),
            SessionPatternDetector(),
            ReworkCorrelationDetector(),
        ]
        log.info("Optimizer started — 6 detectors registered")

    async def stop(self) -> None:
        """Clear context and detector references.

        Idempotent — safe to call multiple times (via _pre_stop override).
        """
        self._context = None
        self._detectors.clear()

    async def shutdown(self) -> None:
        """Final cleanup. No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _run_cycle(self) -> list[OptimizationHypothesis]:
        """Orchestrate all 6 detectors and return sorted hypotheses.

        Steps:
        1. Fetch measurements from Pulse (or return empty if absent).
        2. Run each detector in registration order, isolating failures.
        3. Tag each hypothesis with its detector index for sorting.
        4. Sort by: detector order → confidence desc → generated_at asc.

        Returns:
            A deterministic, sorted list of ``OptimizationHypothesis``.
        """
        units = self._get_measurements()
        tagged: list[tuple[int, OptimizationHypothesis]] = []

        for idx, detector in enumerate(self._detectors):
            try:
                results = detector.detect(units)
                for h in results:
                    tagged.append((idx, h))
            except Exception:  # noqa: BLE001
                log.exception(
                    "Detector %s failed — isolating",
                    type(detector).__name__,
                )
                continue

        return self._sort_hypotheses(tagged)

    def _calculate_baselines(self) -> dict[str, Any]:
        """Compute on-read aggregate baselines from current measurements.

        Returns:
            The evidence dict from BaselineGenerator (containing mean,
            std, min, max per metric), or an empty dict when no data is
            available.
        """
        units = self._get_measurements()
        if not units:
            return {}

        # Find the BaselineGenerator in the detector list
        bg = None
        for d in self._detectors:
            if isinstance(d, BaselineGenerator):
                bg = d
                break

        if bg is None:
            return {}

        try:
            hyps = bg.detect(units)
            return hyps[0].evidence if hyps else {}
        except Exception:  # noqa: BLE001
            log.exception("Baseline computation failed")
            return {}

    # ------------------------------------------------------------------
    # Cross-module services (duck-typed)
    # ------------------------------------------------------------------

    @property
    def services(self) -> dict[str, Callable]:
        """Publish the optimizer API as cross-module services.

        Published contract:
            key:       ``"optimizer.hypotheses"``
            signature: ``() -> list[OptimizationHypothesis]``

            key:       ``"optimizer.baselines"``
            signature: ``() -> dict``

            key:       ``"optimizer.status"``
            signature: ``() -> dict``

        All services are read-only — no state mutation (R10).
        """
        return {
            "optimizer.hypotheses": self._run_cycle,
            "optimizer.baselines": self._calculate_baselines,
            "optimizer.status": self._get_status,
        }

    def _get_status(self) -> dict:
        """Return current optimizer status.

        Returns:
            A dict with ``available``, ``hypothesis_count``,
            ``baseline_count``, and ``pulse_connected``.
        """
        pulse_connected = (
            self._context is not None
            and self._context.services is not None
            and "pulse.measurements" in self._context.services
        )
        hyps = self._run_cycle()
        bl = self._calculate_baselines()
        return {
            "available": True,
            "hypothesis_count": len(hyps),
            "baseline_count": len(bl) if isinstance(bl, dict) else 0,
            "pulse_connected": pulse_connected,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_measurements(self) -> list[Any]:
        """Fetch WorkUnits from Pulse via the cross-module service registry.

        Sentinel pattern (R9, R11):
        - No context → empty list.
        - ``pulse.measurements`` service absent → empty list.
        - Service call fails → empty list.
        - Service returns ``None`` → empty list.
        """
        if self._context is None:
            return []
        try:
            measurements = self._context.services.get("pulse.measurements")
        except Exception:  # noqa: BLE001
            return []
        if measurements is None:
            return []
        try:
            result = measurements()
        except Exception:  # noqa: BLE001
            return []
        return result or []

    @staticmethod
    def _sort_hypotheses(
        tagged: list[tuple[int, OptimizationHypothesis]],
    ) -> list[OptimizationHypothesis]:
        """Sort tagged hypotheses by deterministic order.

        Ordering:
        1. Detector registration order (the index in the tagged tuple).
        2. Within same detector group: confidence descending.
        3. Within same confidence: ``generated_at`` ascending.

        This is a pure, deterministic function.
        """
        tagged.sort(key=lambda x: (x[0], -x[1].confidence, x[1].generated_at))
        return [h for _, h in tagged]


__all__ = [
    "OptimizerModule",
]
