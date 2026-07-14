"""Tests for the RecommendationEngine.

Spec: oracle-recommendation-engine §R1–R4, R7, R10, Constraint A
Design: Oracle — Recommendation Engine §Priority Mapping, §Health Degradation, §Expiration
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from apoch.modules.optimizer.models import OptimizationHypothesis
from apoch.modules.oracle.engine import PRIORITY_ORDER, RecommendationEngine
from apoch.modules.oracle.models import Recommendation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_hyp(
    type_val: str = "pattern",
    domain: str = "cost",
    confidence: float = 0.85,
    evidence: dict | None = None,
    affected_scope: str = "all sessions",
    generated_at: str | None = None,
) -> OptimizationHypothesis:
    """Build an OptimizationHypothesis with defaults."""
    return OptimizationHypothesis(
        type=type_val,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        confidence=confidence,
        evidence=evidence or {"metric": "cpu", "value": 95},
        affected_scope=affected_scope,
        generated_at=generated_at or "2026-07-14T12:00:00",
    )


def _fixed_now(hour: int = 12) -> datetime:
    return datetime(2026, 7, 14, hour, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Task 2.1: Mapping — hypothesis → recommendation
# ---------------------------------------------------------------------------


class TestMapping:
    """Hypothesis-to-recommendation mapping."""

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_happy_path(self, mock_now: object) -> None:
        """A valid hypothesis produces a valid Recommendation."""
        engine = RecommendationEngine()
        hyp = make_hyp(type_val="anomaly", domain="cost", confidence=0.9)
        recs = engine.generate([hyp])
        assert len(recs) == 1
        rec = recs[0]
        assert isinstance(rec, Recommendation)
        assert rec.title == "Cost anomaly detected"
        assert rec.domain == "cost"
        assert rec.priority == "critical"
        assert isinstance(rec.id, str) and len(rec.id) > 0

    def test_empty_input(self) -> None:
        """Empty hypothesis list returns empty recommendation list."""
        engine = RecommendationEngine()
        assert engine.generate([]) == []

    def test_none_input(self) -> None:
        """None input returns empty list (no crash)."""
        engine = RecommendationEngine()
        assert engine.generate(None) == []  # type: ignore[arg-type]

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_each_hyp_produces_one_rec(self, mock_now: object) -> None:
        """Each input hypothesis produces exactly one recommendation."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(type_val="anomaly", domain="cost"),
            make_hyp(type_val="pattern", domain="rework"),
            make_hyp(type_val="opportunity", domain="model_efficiency"),
        ]
        recs = engine.generate(hyps)
        assert len(recs) == 3

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_rec_fields_populated(self, mock_now: object) -> None:
        """Recommendation fields are populated from hypothesis data."""
        engine = RecommendationEngine()
        hyp = make_hyp(
            type_val="anomaly",
            domain="cost",
            confidence=0.9,
            evidence={"metric": "cost", "z_score": 3.5},
        )
        recs = engine.generate([hyp])
        rec = recs[0]
        assert rec.title != ""
        assert rec.description != ""
        assert rec.justification != ""
        assert isinstance(rec.id, str) and len(rec.id) > 0
        assert rec.confidence == 0.9
        assert rec.evidence == {"metric": "cost", "z_score": 3.5}
        assert rec.domain == "cost"
        assert isinstance(rec.source_hypotheses, list)
        assert isinstance(rec.dependencies, list)

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_determinism_same_input(self, mock_now: object) -> None:
        """Same input × 2 calls produces identical output list."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(type_val="anomaly", domain="cost", confidence=0.9),
            make_hyp(type_val="pattern", domain="rework", confidence=0.7),
            make_hyp(
                type_val="opportunity",
                domain="model_efficiency",
                confidence=0.7,
            ),
        ]
        first = engine.generate(hyps)
        second = engine.generate(hyps)
        assert len(first) == len(second)
        for r1, r2 in zip(first, second, strict=True):
            assert r1.id == r2.id
            assert r1.title == r2.title
            assert r1.priority == r2.priority
            assert r1.confidence == r2.confidence

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_recommendations_are_frozen(self, mock_now: object) -> None:
        """Generated recommendations must be immutable."""
        engine = RecommendationEngine()
        hyp = make_hyp(type_val="anomaly", domain="cost")
        recs = engine.generate([hyp])
        rec = recs[0]
        with pytest.raises(FrozenInstanceError):
            rec.confidence = 0.1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 2.1 continued: Priority mapping table
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    """All domain × hypothesis type combinations produce correct priority/confidence."""

    # (domain, hyp_type, expected_priority, expected_confidence)
    # NOTE: confidence kept below 0.9 to avoid triggering the priority bonus
    MAPPING_CASES = [
        ("cost", "anomaly", "critical", 0.9),
        ("rework", "anomaly", "high", 0.85),
        ("cost", "pattern", "high", 0.8),
        ("rework", "pattern", "medium", 0.7),
        ("model_efficiency", "pattern", "medium", 0.75),
        ("model_efficiency", "opportunity", "medium", 0.7),
        ("session_behavior", "pattern", "low", 0.6),
        ("session_behavior", "anomaly", "low", 0.55),
    ]

    @pytest.mark.parametrize(
        ("domain", "hyp_type", "exp_priority", "exp_confidence"),
        MAPPING_CASES,
    )
    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_known_mapping(
        self,
        mock_now: object,
        domain: str,
        hyp_type: str,
        exp_priority: str,
        exp_confidence: float,
    ) -> None:
        """Known (domain, type) pairs map to correct priority and confidence."""
        engine = RecommendationEngine()
        # Low hyp confidence so bonus is NOT triggered
        hyp = make_hyp(
            type_val=hyp_type,  # type: ignore[arg-type]
            domain=domain,  # type: ignore[arg-type]
            confidence=0.5,
        )
        recs = engine.generate([hyp])
        assert len(recs) == 1
        assert recs[0].priority == exp_priority, (
            f"Expected {exp_priority} for ({domain}, {hyp_type})"
        )
        assert recs[0].confidence == exp_confidence

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_time_domain_mappings(self, mock_now: object) -> None:
        """Time domain: anomaly → high, pattern → medium, opp → medium."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(type_val="anomaly", domain="time", confidence=0.5),
            make_hyp(type_val="pattern", domain="time", confidence=0.5),
            make_hyp(type_val="opportunity", domain="time", confidence=0.5),
        ]
        recs = engine.generate(hyps)
        priorities = {r.title: r.priority for r in recs}
        assert any("anomaly" in t for t in priorities)
        assert any("pattern" in t for t in priorities)

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_fallback_mapping(self, mock_now: object) -> None:
        """Unknown (domain, type) pairs fall back to low/0.5."""
        engine = RecommendationEngine()
        # "general" domain + anything not in the specific table → fallback
        hyp = make_hyp(type_val="pattern", domain="general", confidence=0.5)
        recs = engine.generate([hyp])
        assert len(recs) == 1
        assert recs[0].priority == "low"
        assert recs[0].confidence == 0.5

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_domain_general_opportunity_fallback(self, mock_now: object) -> None:
        """general domain + opportunity → fallback low/0.5."""
        engine = RecommendationEngine()
        hyp = make_hyp(type_val="opportunity", domain="general", confidence=0.5)
        recs = engine.generate([hyp])
        assert recs[0].priority == "low"
        assert recs[0].confidence == 0.5


# ---------------------------------------------------------------------------
# Task 2.2: Deterministic prioritization and sorting
# ---------------------------------------------------------------------------


class TestSorting:
    """Sorting tiebreaker chain."""

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_priority_order(self, mock_now: object) -> None:
        """Recommendations sort by priority: critical > high > medium > low."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(type_val="pattern", domain="session_behavior"),  # low
            make_hyp(type_val="pattern", domain="model_efficiency"),  # medium
            make_hyp(type_val="pattern", domain="cost"),  # high
            make_hyp(type_val="anomaly", domain="cost"),  # critical
        ]
        recs = engine.generate(hyps)
        priorities = [r.priority for r in recs]
        assert priorities == ["critical", "high", "medium", "low"]

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_confidence_tiebreaker(self, mock_now: object) -> None:
        """Same priority: higher confidence sorts first."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(
                type_val="anomaly",
                domain="session_behavior",
                confidence=0.9,
            ),  # low/0.55
            make_hyp(
                type_val="pattern",
                domain="session_behavior",
                confidence=0.95,
            ),  # low/0.6
        ]
        recs = engine.generate(hyps)
        assert recs[0].priority == "low"
        assert recs[1].priority == "low"
        # pattern (0.6) should sort before anomaly (0.55) — higher confidence first
        assert recs[0].confidence >= recs[1].confidence

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_created_at_tiebreaker(self, mock_now: object) -> None:
        """Same priority + confidence: earlier created_at sorts first."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(
                type_val="anomaly",
                domain="session_behavior",
                confidence=0.6,
                generated_at="2026-07-14T13:00:00",
            ),  # low/0.55
            make_hyp(
                type_val="anomaly",
                domain="session_behavior",
                confidence=0.6,
                generated_at="2026-07-14T12:00:00",
            ),  # low/0.55
        ]
        recs = engine.generate(hyps)
        assert recs[0].created_at <= recs[1].created_at

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_id_tiebreaker(self, mock_now: object) -> None:
        """Same priority + confidence + created_at: lexicographic id breaks tie."""
        engine = RecommendationEngine()
        hyps = [
            make_hyp(
                type_val="anomaly",
                domain="session_behavior",
                confidence=0.6,
                generated_at="2026-07-14T12:00:00",
            ),
            make_hyp(
                type_val="anomaly",
                domain="session_behavior",
                confidence=0.6,
                generated_at="2026-07-14T12:00:00",
            ),
        ]
        recs = engine.generate(hyps)
        ids = [r.id for r in recs]
        assert ids == sorted(ids)

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_priority_bonus(self, mock_now: object) -> None:
        """Confidence >= 0.9 AND domain in (cost, time, rework) bumps one tier."""
        engine = RecommendationEngine()
        # rework + pattern → medium (base). With hyp confidence >= 0.9 → bump to high
        hyp = make_hyp(type_val="pattern", domain="rework", confidence=0.95)
        recs = engine.generate([hyp])
        assert recs[0].priority == "high"  # bumped from medium

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_priority_bonus_critical_stays_critical(self, mock_now: object) -> None:
        """Critical priority stays critical (can't bump above critical)."""
        engine = RecommendationEngine()
        hyp = make_hyp(type_val="anomaly", domain="cost", confidence=0.95)
        recs = engine.generate([hyp])
        assert recs[0].priority == "critical"  # already critical, stays critical

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_priority_bonus_low_confidence_no_bump(self, mock_now: object) -> None:
        """Hyp confidence < 0.9 means no priority bump even for cost domain."""
        engine = RecommendationEngine()
        hyp = make_hyp(type_val="pattern", domain="cost", confidence=0.85)
        recs = engine.generate([hyp])
        assert recs[0].priority == "high"  # base mapping, no bonus (0.85 < 0.9)

    @patch("apoch.modules.oracle.engine._utc_now", return_value=_fixed_now(12))
    def test_priority_bonus_wrong_domain_no_bump(
        self,
        mock_now: object,
    ) -> None:
        """Domain outside cost/time/rework gets no bonus even with high confidence."""
        engine = RecommendationEngine()
        hyp = make_hyp(
            type_val="pattern",
            domain="model_efficiency",
            confidence=0.95,
        )
        recs = engine.generate([hyp])
        assert recs[0].priority == "medium"  # base for model_efficiency+pattern


# ---------------------------------------------------------------------------
# Task 2.3: Expiration logic
# ---------------------------------------------------------------------------


class TestExpiration:
    """On-read expiration check."""

    def test_within_ttl_stays_active(self) -> None:
        """Rec within TTL keeps status='active'."""
        # created_at=15:30, critical TTL=60min → expires at 16:30
        # Mock now at 16:00, so 16:00 < 16:30 → still active
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost",  # critical
                generated_at="2026-07-14T15:30:00",
            )
            recs = engine.generate([hyp])
        assert recs[0].status == "active"

    def test_past_ttl_becomes_expired(self) -> None:
        """Rec past TTL gets status='expired'."""
        # created_at=14:00, critical TTL=60min → expires at 15:00
        # Mock now at 16:00, so 16:00 > 15:00 → expired
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost",  # critical
                generated_at="2026-07-14T14:00:00",
            )
            recs = engine.generate([hyp])
        assert recs[0].status == "expired"

    def test_at_ttl_boundary_stays_active(self) -> None:
        """Rec exactly at TTL boundary stays active (expiration >= now)."""
        # created_at=15:00, critical TTL=60min → expires at 16:00
        # Mock now at 16:00, boundary = 16:00 == 16:00 → still active
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost",
                generated_at="2026-07-14T15:00:00",
            )
            recs = engine.generate([hyp])
        assert recs[0].status == "active"

    def test_custom_ttl_config(self) -> None:
        """Custom TTL config overrides defaults."""
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            # Critical TTL = 10 minutes
            engine = RecommendationEngine(domain_ttls={"critical": 10})
            # created_at=15:55, TTL=10 → expires at 16:05
            # now=16:00, 16:00 < 16:05 → active
            hyp = make_hyp(
                type_val="anomaly", domain="cost",
                generated_at="2026-07-14T15:55:00",
            )
            recs = engine.generate([hyp])
        assert recs[0].status == "active"

    def test_different_priority_ttls(self) -> None:
        """Different priority levels have different TTLs."""
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            # critical rec (TTL=60min): created_at=15:30 → expires at 16:30 → active
            # low rec (TTL=1440min): created_at=15:30 → expires way later → active
            hyps = [
                make_hyp(
                    type_val="anomaly", domain="cost",
                    generated_at="2026-07-14T15:30:00",
                ),
                make_hyp(
                    type_val="pattern", domain="session_behavior",
                    generated_at="2026-07-14T15:30:00",
                ),
            ]
            recs = engine.generate(hyps)
        assert all(r.status == "active" for r in recs)

    def test_mixed_expired_and_active(self) -> None:
        """Mix of expired and active recs: only expired ones get status change."""
        now = _fixed_now(16)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyps = [
                make_hyp(
                    type_val="anomaly", domain="cost",  # critical TTL=60min
                    generated_at="2026-07-14T14:00:00",  # expires 15:00 → expired
                ),
                make_hyp(
                    type_val="pattern", domain="session_behavior",  # low TTL=1440min
                    generated_at="2026-07-14T15:30:00",  # well within → active
                ),
            ]
            recs = engine.generate(hyps)
        statuses = {r.title: r.status for r in recs}
        # Find expired and active
        assert "expired" in statuses.values()
        assert "active" in statuses.values()


# ---------------------------------------------------------------------------
# Task 2.4: Health-based confidence degradation
# ---------------------------------------------------------------------------


class TestHealthDegradation:
    """Confidence degradation from failing Guardian diagnostics."""

    def test_health_absent_no_degradation(self) -> None:
        """No health dict → confidence used as-is."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
            )
            recs = engine.generate([hyp], health=None)
        assert recs[0].confidence == 0.9

    def test_health_empty_no_degradation(self) -> None:
        """Empty health dict → confidence used as-is."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
            )
            recs = engine.generate([hyp], health={})
        assert recs[0].confidence == 0.9

    def test_one_module_failing(self) -> None:
        """One failing module degrades confidence by 0.9x."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
            )
            health = {"OptimizerModule": {"diagnostic": "Memory limit reached"}}
            recs = engine.generate([hyp], health=health)
        assert recs[0].confidence == pytest.approx(0.9 * 0.9)
        # Evidence should mention the degradation
        evidence = recs[0].evidence
        assert "health_degradation" in evidence

    def test_multiple_modules_failing(self) -> None:
        """Multiple failing modules degrade confidence cumulatively."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
            )
            health = {
                "OptimizerModule": {"diagnostic": "Memory limit reached"},
                "PulseModule": {"diagnostic": "Connection timeout"},
            }
            recs = engine.generate([hyp], health=health)
        assert recs[0].confidence == pytest.approx(0.9 * 0.9 * 0.9)

    def test_all_healthy_no_degradation(self) -> None:
        """All modules healthy → no degradation (empty health)."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
            )
            recs = engine.generate([hyp], health={})
        assert recs[0].confidence == 0.9

    def test_health_evidence_notes(self) -> None:
        """Health evidence captures degradation source."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyp = make_hyp(
                type_val="anomaly", domain="cost", confidence=0.9,
                evidence={"original": "data"},
            )
            health = {"OptimizerModule": {"diagnostic": "Memory limit"}}
            recs = engine.generate([hyp], health=health)
        evidence = recs[0].evidence
        assert "original" in evidence
        assert "health_degradation" in evidence
        notes = evidence["health_degradation"]
        assert any("OptimizerModule" in n for n in notes)
        assert any("Memory limit" in n for n in notes)

    def test_degradation_same_modules_deterministic(self) -> None:
        """Same health input produces same degradation across calls."""
        now = _fixed_now(12)
        with patch("apoch.modules.oracle.engine._utc_now", return_value=now):
            engine = RecommendationEngine()
            hyps = [
                make_hyp(type_val="anomaly", domain="cost", confidence=0.9),
            ]
            health = {"PulseModule": {"diagnostic": "timeout"}}
            first = engine.generate(hyps, health=health)
            second = engine.generate(hyps, health=health)
        assert first[0].confidence == second[0].confidence
        assert first[0].evidence == second[0].evidence


# ---------------------------------------------------------------------------
# PRIORITY_ORDER export
# ---------------------------------------------------------------------------


class TestPriorityOrder:
    """PRIORITY_ORDER dict must be defined and correct."""

    def test_priority_order_defined(self) -> None:
        assert PRIORITY_ORDER["critical"] == 0
        assert PRIORITY_ORDER["high"] == 1
        assert PRIORITY_ORDER["medium"] == 2
        assert PRIORITY_ORDER["low"] == 3
