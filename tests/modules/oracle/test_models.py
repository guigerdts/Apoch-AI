"""Tests for Oracle domain models.

Spec: oracle-recommendation-engine §R4, R9, R11
Design: Oracle — Recommendation Engine §Data Model
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from apoch.modules.oracle.models import Recommendation


class TestRecommendation:
    """Recommendation is the output contract (§R4)."""

    def test_construct_with_all_fields(self) -> None:
        """A recommendation MUST carry all 13 fields."""
        rec = Recommendation(
            id="550e8400-e29b-41d4-a716-446655440000",
            title="High cost anomaly detected",
            description="Cost metric exceeds 3σ threshold",
            priority="critical",
            confidence=0.95,
            evidence={"metric": "cost", "z_score": 4.2},
            justification="Cost metric exceeds 3σ for 3 consecutive windows",
            dependencies=["pulse.measurements"],
            expiration="2026-07-14T13:00:00",
            source_hypotheses=["hyp-001"],
            domain="cost",
            status="active",
            created_at="2026-07-14T12:00:00",
        )
        assert rec.id == "550e8400-e29b-41d4-a716-446655440000"
        assert rec.title == "High cost anomaly detected"
        assert rec.description == "Cost metric exceeds 3σ threshold"
        assert rec.priority == "critical"
        assert rec.confidence == 0.95
        assert rec.evidence == {"metric": "cost", "z_score": 4.2}
        assert rec.justification == "Cost metric exceeds 3σ for 3 consecutive windows"
        assert rec.dependencies == ["pulse.measurements"]
        assert rec.expiration == "2026-07-14T13:00:00"
        assert rec.source_hypotheses == ["hyp-001"]
        assert rec.domain == "cost"
        assert rec.status == "active"
        assert rec.created_at == "2026-07-14T12:00:00"

    def test_frozen_immutability(self) -> None:
        """Recommendation MUST be frozen (immutable)."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status="active", created_at="now",
        )
        with pytest.raises(FrozenInstanceError):
            rec.confidence = 0.9  # type: ignore[misc]

    @pytest.mark.parametrize("priority", ["critical", "high", "medium", "low"])
    def test_all_priorities(self, priority: str) -> None:
        """priority MUST be one of the four valid values."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority=priority,  # type: ignore[arg-type]
            confidence=0.5, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status="active", created_at="now",
        )
        assert rec.priority == priority

    @pytest.mark.parametrize("domain", [
        "cost", "time", "rework", "model_efficiency", "session_behavior", "general",
    ])
    def test_all_domains(self, domain: str) -> None:
        """domain MUST be one of the six valid values."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain=domain,  # type: ignore[arg-type]
            status="active", created_at="now",
        )
        assert rec.domain == domain

    @pytest.mark.parametrize("status_val", ["active", "accepted", "rejected", "expired"])
    def test_all_statuses(self, status_val: str) -> None:
        """status MUST be one of the four valid values."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status=status_val,  # type: ignore[arg-type]
            created_at="now",
        )
        assert rec.status == status_val

    def test_empty_lists(self) -> None:
        """dependencies and source_hypotheses MAY be empty lists."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={},
            justification="j", dependencies=[],
            expiration="now", source_hypotheses=[],
            domain="general", status="active", created_at="now",
        )
        assert rec.dependencies == []
        assert rec.source_hypotheses == []

    def test_confidence_boundaries(self) -> None:
        """confidence MUST accept 0.0 and 1.0 boundaries."""
        rec_0 = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.0, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status="active", created_at="now",
        )
        assert rec_0.confidence == 0.0

        rec_1 = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=1.0, evidence={},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status="active", created_at="now",
        )
        assert rec_1.confidence == 1.0

    def test_evidence_is_dict(self) -> None:
        """evidence MUST be a dict."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={"key": "value"},
            justification="j", dependencies=[], expiration="now",
            source_hypotheses=[], domain="general",
            status="active", created_at="now",
        )
        assert isinstance(rec.evidence, dict)

    def test_str_fields_are_str(self) -> None:
        """String fields MUST be string type."""
        rec = Recommendation(
            id="my-id", title="my-title", description="my-desc",
            priority="low", confidence=0.5, evidence={},
            justification="my-justification", dependencies=[],
            expiration="2026-07-14T13:00:00",
            source_hypotheses=[], domain="general",
            status="active", created_at="2026-07-14T12:00:00",
        )
        assert isinstance(rec.id, str)
        assert isinstance(rec.title, str)
        assert isinstance(rec.description, str)
        assert isinstance(rec.justification, str)
        assert isinstance(rec.expiration, str)
        assert isinstance(rec.created_at, str)

    def test_lists_are_lists(self) -> None:
        """dependencies and source_hypotheses MUST be lists."""
        rec = Recommendation(
            id="id", title="t", description="d",
            priority="low", confidence=0.5, evidence={},
            justification="j", dependencies=["dep1"],
            expiration="now", source_hypotheses=["hyp-001"],
            domain="general", status="active", created_at="now",
        )
        assert isinstance(rec.dependencies, list)
        assert isinstance(rec.source_hypotheses, list)
