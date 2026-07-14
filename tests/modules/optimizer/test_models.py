"""Tests for Optimizer domain models and confidence helpers.

Spec: optimizer-engineering-optimization §R7, R8
Design: Optimizer — Engineering Optimization Intelligence §Data Model, §Confidence Scoring
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from apoch.modules.optimizer._confidence import cap_underpowered
from apoch.modules.optimizer.models import OptimizationHypothesis


class TestOptimizationHypothesis:
    """OptimizationHypothesis is the output contract (§R7)."""

    def test_construct_with_all_fields(self) -> None:
        """A hypothesis MUST carry type, domain, confidence, evidence,
        affected_scope, and generated_at."""
        h = OptimizationHypothesis(
            type="pattern",
            domain="cost",
            confidence=0.85,
            evidence={"mean": 100.0, "std": 10.0},
            affected_scope="all sessions",
            generated_at="2026-07-14T12:00:00",
        )
        assert h.type == "pattern"
        assert h.domain == "cost"
        assert h.confidence == 0.85
        assert h.evidence == {"mean": 100.0, "std": 10.0}
        assert h.affected_scope == "all sessions"
        assert h.generated_at == "2026-07-14T12:00:00"

    def test_construct_anomaly_type(self) -> None:
        """type MAY be 'anomaly'."""
        h = OptimizationHypothesis(
            type="anomaly", domain="time",
            confidence=0.9, evidence={},
            affected_scope="scope", generated_at="now",
        )
        assert h.type == "anomaly"

    def test_construct_opportunity_type(self) -> None:
        """type MAY be 'opportunity'."""
        h = OptimizationHypothesis(
            type="opportunity", domain="rework",
            confidence=0.7, evidence={},
            affected_scope="scope", generated_at="now",
        )
        assert h.type == "opportunity"

    @pytest.mark.parametrize("domain", [
        "cost", "time", "rework", "model_efficiency", "session_behavior",
    ])
    def test_all_domains(self, domain: str) -> None:
        """domain MUST be one of the five valid domains."""
        h = OptimizationHypothesis(
            type="pattern", domain=domain,  # type: ignore[arg-type]
            confidence=0.5, evidence={},
            affected_scope="scope", generated_at="now",
        )
        assert h.domain == domain

    def test_frozen_immutability(self) -> None:
        """OptimizationHypothesis MUST be frozen (immutable)."""
        h = OptimizationHypothesis(
            type="pattern", domain="cost",
            confidence=0.5, evidence={},
            affected_scope="scope", generated_at="now",
        )
        with pytest.raises(FrozenInstanceError):
            h.confidence = 0.9  # type: ignore[misc]

    def test_confidence_in_range(self) -> None:
        """confidence MUST be 0.0-1.0 (enforced at construction)."""
        OptimizationHypothesis(
            type="pattern", domain="cost",
            confidence=0.0, evidence={},
            affected_scope="scope", generated_at="now",
        )
        OptimizationHypothesis(
            type="pattern", domain="cost",
            confidence=1.0, evidence={},
            affected_scope="scope", generated_at="now",
        )

    def test_evidence_is_dict(self) -> None:
        """evidence MUST be a dict."""
        h = OptimizationHypothesis(
            type="pattern", domain="cost",
            confidence=0.5,
            evidence={"key": "value"},
            affected_scope="scope", generated_at="now",
        )
        assert isinstance(h.evidence, dict)

    def test_affected_scope_is_str(self) -> None:
        """affected_scope MUST be a string."""
        h = OptimizationHypothesis(
            type="pattern", domain="cost",
            confidence=0.5, evidence={},
            affected_scope="model: claude-4", generated_at="now",
        )
        assert isinstance(h.affected_scope, str)


class TestCapUnderpowered:
    """cap_underpowered caps confidence when data is insufficient (§R8)."""

    def test_n_less_than_3_caps_at_0_5(self) -> None:
        """When n < 3, cap at 0.5."""
        assert cap_underpowered(0.9, 1) == 0.5
        assert cap_underpowered(0.9, 2) == 0.5

    def test_n_equal_3_no_cap(self) -> None:
        """When n >= 3, score is unchanged."""
        assert cap_underpowered(0.9, 3) == 0.9

    def test_n_greater_than_3_no_cap(self) -> None:
        """When n > 3, score is unchanged."""
        assert cap_underpowered(0.9, 10) == 0.9

    def test_score_already_below_cap_unchanged(self) -> None:
        """When score is already below the cap, it stays as-is."""
        assert cap_underpowered(0.3, 1) == 0.3

    def test_clamp_at_0(self) -> None:
        """Negative scores MUST be clamped to 0.0."""
        assert cap_underpowered(-0.1, 5) == 0.0

    def test_clamp_at_1(self) -> None:
        """Scores above 1.0 MUST be clamped to 1.0."""
        assert cap_underpowered(1.5, 5) == 1.0

    def test_deterministic(self) -> None:
        """Given same inputs, cap_underpowered MUST return same result."""
        for _ in range(10):
            assert cap_underpowered(0.75, 5) == 0.75

    def test_n_less_than_3_does_not_increase_score(self) -> None:
        """When n < 3 and score is below 0.5, it stays the same (not increased)."""
        assert cap_underpowered(0.2, 1) == 0.2
        assert cap_underpowered(0.4, 2) == 0.4
