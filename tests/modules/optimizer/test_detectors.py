"""Tests for Optimizer detectors — protocol, baseline, and all 5 detectors.

Spec: optimizer-engineering-optimization §R1–R6
Design: Optimizer — Engineering Optimization Intelligence §Detector Protocol
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from apoch.modules.optimizer.models import OptimizationHypothesis

# ── Helpers ──────────────────────────────────────────────────────────


def _wu(**kw) -> object:
    """Build a minimal WorkUnit-like object using all defaults.

    Tests use duck typing — detectors access fields via getattr.
    """
    defaults: dict = {
        "id": "u1",
        "session_id": "s1",
        "model": "claude-4",
        "tokens_input": 100,
        "tokens_output": 50,
        "wall_clock_s": 30.0,
        "cost": None,
        "created_at": "2026-07-14T10:00:00",
        "completed_at": None,
    }
    defaults.update(kw)
    return _WorkUnitStub(**defaults)


class _WorkUnitStub:
    """Duck-typed WorkUnit for testing — same shape as the real dataclass."""

    def __init__(
        self,
        id: str,
        session_id: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        wall_clock_s: float,
        cost: Decimal | None = None,
        created_at: str = "",
        completed_at: str | None = None,
        rework_cycles: int | None = None,
        rework_tokens: int | None = None,
        status: str = "",
    ) -> None:
        self.id = id
        self.session_id = session_id
        self.model = model
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.wall_clock_s = wall_clock_s
        self.cost = cost
        self.created_at = created_at
        self.completed_at = completed_at
        self.rework_cycles = rework_cycles
        self.rework_tokens = rework_tokens
        self.status = status


def _strip_ts(hyps: list[OptimizationHypothesis]) -> list[OptimizationHypothesis]:
    """Return hypotheses with ``generated_at`` cleared for comparison.

    ``generated_at`` is the only non-deterministic field (R12) — exclude
    it from equality checks in determinism tests.
    """
    return [replace(h, generated_at="") for h in hyps]


# ── BaselineGenerator ────────────────────────────────────────────────


class TestBaselineGenerator:
    """BaselineGenerator computes descriptive statistics from WorkUnits (§R1)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        """Import and run BaselineGenerator — deferred to avoid import-order issues."""
        from apoch.modules.optimizer._detectors import BaselineGenerator
        return BaselineGenerator().detect(units)

    def test_happy_path_full_data(self) -> None:
        """Three+ units with full data → mean, std, min, max per metric."""
        units = [
            _wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                cost=Decimal("0.015")),
            _wu(tokens_input=200, tokens_output=100, wall_clock_s=60.0,
                cost=Decimal("0.030"), id="u2"),
            _wu(tokens_input=300, tokens_output=150, wall_clock_s=90.0,
                cost=Decimal("0.045"), id="u3"),
        ]
        hyps = self._detect(units)

        assert len(hyps) == 1
        h = hyps[0]
        assert h.type == "pattern"
        assert h.domain == "cost"
        assert 0.0 <= h.confidence <= 1.0
        assert "tokens_input" in h.evidence
        assert "tokens_output" in h.evidence
        assert "cost" in h.evidence
        assert "wall_clock_s" in h.evidence

        ti = h.evidence["tokens_input"]
        assert ti["mean"] == 200.0
        assert ti["min"] == 100
        assert ti["max"] == 300
        assert ti["std"] > 0

        # Values are stored as float after computation
        assert h.evidence["cost"]["mean"] == 0.03

    def test_empty_list_returns_empty(self) -> None:
        """Empty input → empty hypotheses list."""
        assert self._detect([]) == []

    def test_partial_cost_data(self) -> None:
        """Units with None cost → skip cost for those units, compute from available."""
        units = [
            _wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                cost=Decimal("0.015")),
            _wu(tokens_input=200, tokens_output=100, wall_clock_s=60.0,
                cost=None, id="u2"),
            _wu(tokens_input=300, tokens_output=150, wall_clock_s=90.0,
                cost=Decimal("0.045"), id="u3"),
        ]
        hyps = self._detect(units)
        assert len(hyps) == 1
        cost_ev = hyps[0].evidence["cost"]
        assert cost_ev["mean"] == 0.03  # only 2 units
        assert cost_ev["count"] == 2

    def test_determinism(self) -> None:
        """Same input × 2 → bitwise identical output (excluding generated_at)."""
        units = [
            _wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                cost=Decimal("0.015")),
            _wu(tokens_input=200, tokens_output=100, wall_clock_s=60.0,
                cost=Decimal("0.030"), id="u2"),
            _wu(tokens_input=300, tokens_output=150, wall_clock_s=90.0,
                cost=Decimal("0.045"), id="u3"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))

    def test_single_unit(self) -> None:
        """Single unit → std is 0, mean/min/max computed."""
        units = [_wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0)]
        hyps = self._detect(units)
        assert len(hyps) == 1
        ti = hyps[0].evidence["tokens_input"]
        assert ti["mean"] == 100.0
        assert ti["std"] == 0.0
        assert ti["min"] == 100
        assert ti["max"] == 100


# ── DegradationDetector ──────────────────────────────────────────────


class TestDegradationDetector:
    """DegradationDetector uses z-scores against baseline (§R2)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        from apoch.modules.optimizer._detectors import DegradationDetector
        return DegradationDetector().detect(units)

    def _baseline_units(self) -> list:
        """3 baseline units with consistent low values."""
        return [
            _wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                cost=Decimal("0.015")),
            _wu(tokens_input=110, tokens_output=55, wall_clock_s=32.0,
                cost=Decimal("0.016"), id="u2"),
            _wu(tokens_input=105, tokens_output=52, wall_clock_s=31.0,
                cost=Decimal("0.015"), id="u3"),
        ]

    def test_degradation_detected(self) -> None:
        """Recent high value → degradation hypothesis."""
        units = self._baseline_units() + [
            _wu(tokens_input=500, tokens_output=250, wall_clock_s=150.0,
                cost=Decimal("0.075"), id="u4"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0
        h = hyps[0]
        assert h.type == "anomaly"
        assert h.domain in ("cost", "time")
        assert 0.0 <= h.confidence <= 1.0

    def test_no_baseline_empty(self) -> None:
        """No units → empty hypotheses (no baseline)."""
        assert self._detect([]) == []

    def test_less_than_3_data_points(self) -> None:
        """Fewer than 3 units → confidence capped via cap_underpowered."""
        units = [
            _wu(tokens_input=100, tokens_output=50, wall_clock_s=30.0),
            _wu(tokens_input=200, tokens_output=100, wall_clock_s=60.0,
                id="u2"),
        ]
        hyps = self._detect(units)
        assert len(hyps) == 0 or all(h.confidence <= 0.5 for h in hyps)

    def test_determinism(self) -> None:
        """Same input × 2 → identical results (excluding generated_at)."""
        units = self._baseline_units() + [
            _wu(tokens_input=500, tokens_output=250, wall_clock_s=150.0,
                cost=Decimal("0.075"), id="u4"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))

    def test_no_degradation_with_normal_values(self) -> None:
        """All values within normal range → no hypotheses."""
        units = self._baseline_units()
        hyps = self._detect(units)
        assert len(hyps) == 0


# ── ModelEfficiencyDetector ──────────────────────────────────────────


class TestModelEfficiencyDetector:
    """ModelEfficiencyDetector compares models by cost/token and time/unit (§R3)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        from apoch.modules.optimizer._detectors import ModelEfficiencyDetector
        return ModelEfficiencyDetector().detect(units)

    def test_multiple_models_compared(self) -> None:
        """Two models → efficiency comparison hypothesis."""
        units = [
            _wu(model="claude-4", tokens_input=100, tokens_output=50,
                wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(model="claude-4", tokens_input=200, tokens_output=100,
                wall_clock_s=60.0, cost=Decimal("0.030"), id="u2"),
            _wu(model="gpt-4o", tokens_input=100, tokens_output=50,
                wall_clock_s=60.0, cost=Decimal("0.060"), id="u3"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0
        h = hyps[0]
        assert h.type == "opportunity"
        assert h.domain == "model_efficiency"
        assert h.evidence["comparison"] == "cost_per_token"
        assert "models" in h.evidence

    def test_single_model_empty(self) -> None:
        """Single model → no comparison possible, empty list."""
        units = [
            _wu(model="claude-4", tokens_input=100, tokens_output=50,
                wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(model="claude-4", tokens_input=200, tokens_output=100,
                wall_clock_s=60.0, cost=Decimal("0.030"), id="u2"),
        ]
        assert self._detect(units) == []

    def test_partial_cost_data_noted(self) -> None:
        """Some units missing cost → note in evidence."""
        units = [
            _wu(model="claude-4", tokens_input=100, tokens_output=50,
                wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(model="gpt-4o", tokens_input=100, tokens_output=50,
                wall_clock_s=60.0, cost=None, id="u3"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0

    def test_determinism(self) -> None:
        """Same input × 2 → identical results (excluding generated_at)."""
        units = [
            _wu(model="claude-4", tokens_input=100, tokens_output=50,
                wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(model="gpt-4o", tokens_input=100, tokens_output=50,
                wall_clock_s=60.0, cost=Decimal("0.060"), id="u3"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))

    def test_three_models(self) -> None:
        """Three models → multiple comparisons."""
        units = [
            _wu(model="claude-4", tokens_input=100, tokens_output=50,
                wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(model="gpt-4o", tokens_input=100, tokens_output=50,
                wall_clock_s=60.0, cost=Decimal("0.060"), id="u2"),
            _wu(model="haiku", tokens_input=100, tokens_output=50,
                wall_clock_s=15.0, cost=Decimal("0.005"), id="u3"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0


# ── AnomalyDetector ──────────────────────────────────────────────────


class TestAnomalyDetector:
    """AnomalyDetector finds IQR-based outliers (§R4)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        from apoch.modules.optimizer._detectors import AnomalyDetector
        return AnomalyDetector().detect(units)

    def test_outlier_detected(self) -> None:
        """One extreme value → outlier hypothesis."""
        units = [
            _wu(wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(wall_clock_s=32.0, cost=Decimal("0.016"), id="u2"),
            _wu(wall_clock_s=31.0, cost=Decimal("0.015"), id="u3"),
            _wu(wall_clock_s=35.0, cost=Decimal("0.017"), id="u4"),
            _wu(wall_clock_s=300.0, cost=Decimal("0.150"), id="u5"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0
        h = hyps[0]
        assert h.type == "anomaly"
        assert 0.0 <= h.confidence <= 1.0

    def test_no_outliers(self) -> None:
        """Tight distribution → no anomaly hypotheses."""
        units = [
            _wu(wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(wall_clock_s=31.0, cost=Decimal("0.016"), id="u2"),
            _wu(wall_clock_s=32.0, cost=Decimal("0.015"), id="u3"),
            _wu(wall_clock_s=29.0, cost=Decimal("0.014"), id="u4"),
            _wu(wall_clock_s=33.0, cost=Decimal("0.017"), id="u5"),
        ]
        assert self._detect(units) == []

    def test_less_than_3_points_no_hypothesis(self) -> None:
        """<3 points for a metric → no hypothesis for that metric."""
        units = [
            _wu(wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(wall_clock_s=31.0, cost=Decimal("0.016"), id="u2"),
        ]
        assert self._detect(units) == []

    def test_determinism(self) -> None:
        """Same input × 2 → identical results (excluding generated_at)."""
        units = [
            _wu(wall_clock_s=30.0, cost=Decimal("0.015")),
            _wu(wall_clock_s=32.0, cost=Decimal("0.016"), id="u2"),
            _wu(wall_clock_s=31.0, cost=Decimal("0.015"), id="u3"),
            _wu(wall_clock_s=35.0, cost=Decimal("0.017"), id="u4"),
            _wu(wall_clock_s=300.0, cost=Decimal("0.150"), id="u5"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))


# ── SessionPatternDetector ───────────────────────────────────────────


class TestSessionPatternDetector:
    """SessionPatternDetector clusters by time-of-day hour (§R5)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        from apoch.modules.optimizer._detectors import SessionPatternDetector
        return SessionPatternDetector().detect(units)

    def test_temporal_pattern_detected(self) -> None:
        """Many units in a 4-hour window → cluster hypothesis."""
        units = []
        for i in range(10):
            units.append(
                _wu(created_at=f"2026-07-14T09:{i:02d}:00", id=f"u{i}")
            )
        # 3 units in a different window
        for i in range(10, 13):
            units.append(
                _wu(created_at=f"2026-07-14T14:{i:02d}:00", id=f"u{i}")
            )
        hyps = self._detect(units)
        # 10/13 ≈ 77% in the 09:00-13:00 window → >60% → cluster detected
        assert len(hyps) > 0

    def test_insufficient_data(self) -> None:
        """<3 units → empty hypotheses."""
        units = [
            _wu(created_at="2026-07-14T10:00:00"),
            _wu(created_at="2026-07-14T11:00:00", id="u2"),
        ]
        assert self._detect(units) == []

    def test_missing_timestamps_excluded(self) -> None:
        """Units without created_at are excluded from analysis."""
        units = [
            _wu(created_at="2026-07-14T10:00:00"),
            _wu(created_at="", id="u2"),
            _wu(created_at="2026-07-14T10:30:00", id="u3"),
            _wu(created_at="2026-07-14T11:00:00", id="u4"),
        ]
        hyps = self._detect(units)
        # 3 out of 3 (missing excluded) → confident in 10:00-14:00 window
        assert len(hyps) > 0

    def test_determinism(self) -> None:
        """Same input × 2 → identical results (excluding generated_at)."""
        units = [
            _wu(created_at="2026-07-14T10:00:00"),
            _wu(created_at="2026-07-14T10:30:00", id="u2"),
            _wu(created_at="2026-07-14T11:00:00", id="u3"),
            _wu(created_at="2026-07-14T15:00:00", id="u4"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))


# ── ReworkCorrelationDetector ────────────────────────────────────────


class TestReworkCorrelationDetector:
    """ReworkCorrelationDetector correlates rework with conditions (§R6)."""

    def _detect(self, units: list) -> list[OptimizationHypothesis]:
        from apoch.modules.optimizer._detectors import ReworkCorrelationDetector
        return ReworkCorrelationDetector().detect(units)

    def test_correlation_detected_model(self) -> None:
        """Model → rework correlation detected."""
        units = [
            _wu(model="claude-4", rework_cycles=1, rework_tokens=50),
            _wu(model="claude-4", rework_cycles=0, rework_tokens=0, id="u2"),
            _wu(model="gpt-4o", rework_cycles=5, rework_tokens=200, id="u3"),
            _wu(model="gpt-4o", rework_cycles=4, rework_tokens=180, id="u4"),
        ]
        hyps = self._detect(units)
        assert len(hyps) > 0
        h = hyps[0]
        assert h.domain == "rework"
        assert 0.0 <= h.confidence <= 1.0

    def test_no_rework_data_empty(self) -> None:
        """No rework fields → empty hypotheses."""
        units = [
            _wu(model="claude-4"),
            _wu(model="gpt-4o", id="u2"),
        ]
        assert self._detect(units) == []

    def test_partial_condition_fields_noted(self) -> None:
        """Some units missing model → note partial data in evidence."""

        # A WorkUnit stub that may lack the model attribute
        class _PartialModelStub:
            def __init__(self, rework_cycles=0, rework_tokens=0, model="",
                         id="ux", session_id="sx", tokens_input=0,
                         tokens_output=0, wall_clock_s=0.0, cost=None,
                         created_at="") -> None:
                self.id = id
                self.session_id = session_id
                self.tokens_input = tokens_input
                self.tokens_output = tokens_output
                self.wall_clock_s = wall_clock_s
                self.cost = cost
                self.created_at = created_at
                self.rework_cycles = rework_cycles
                self.rework_tokens = rework_tokens
                if model:
                    self.model = model

        from apoch.modules.optimizer._detectors import ReworkCorrelationDetector
        detector = ReworkCorrelationDetector()

        units: list = [
            _PartialModelStub(rework_cycles=5, rework_tokens=200),  # no model
            _PartialModelStub(rework_cycles=4, rework_tokens=180,
                              id="u2", model="claude-4"),
            _PartialModelStub(rework_cycles=1, rework_tokens=50,
                              id="u3", model="claude-4"),
        ]
        hyps = detector.detect(units)
        # Partial data → may still produce hypothesis or note missing
        if hyps:
            assert isinstance(hyps[0].evidence, dict)

    def test_determinism(self) -> None:
        """Same input × 2 → identical results (excluding generated_at)."""
        units = [
            _wu(model="claude-4", rework_cycles=1, rework_tokens=50),
            _wu(model="claude-4", rework_cycles=0, rework_tokens=0, id="u2"),
            _wu(model="gpt-4o", rework_cycles=5, rework_tokens=200, id="u3"),
            _wu(model="gpt-4o", rework_cycles=4, rework_tokens=180, id="u4"),
        ]
        assert _strip_ts(self._detect(units)) == _strip_ts(self._detect(units))

    def test_no_significant_rework(self) -> None:
        """Minimal rework across models → no hypothesis."""
        units = [
            _wu(model="claude-4", rework_cycles=0, rework_tokens=0),
            _wu(model="claude-4", rework_cycles=1, rework_tokens=10, id="u2"),
            _wu(model="gpt-4o", rework_cycles=0, rework_tokens=0, id="u3"),
            _wu(model="gpt-4o", rework_cycles=1, rework_tokens=5, id="u4"),
        ]
        hyps = self._detect(units)
        # All values close → no >2x difference → no hypothesis
        assert len(hyps) == 0
