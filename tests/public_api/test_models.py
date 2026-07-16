"""Tests for public API models (RED phase: classes don't exist yet).

Spec: mcp-public-api §ToolResponse format, §EvidenceSource
Design: ADR-002, ADR-003
"""

from datetime import UTC, datetime

import pytest


class TestEvidenceSource:
    """EvidenceSource dataclass construction and attributes."""

    def test_construction_with_all_fields(self):
        """EvidenceSource stores all 4 fields as provided."""
        from apoch.public_api.models import EvidenceSource

        source = EvidenceSource(
            source="Vision",
            confidence=0.85,
            collected_ago=30,
            based_on="38 work units",
        )

        assert source.source == "Vision"
        assert source.confidence == 0.85
        assert source.collected_ago == 30
        assert source.based_on == "38 work units"

    def test_confidence_is_float_in_range(self):
        """Confidence is stored as float; values must be 0.0-1.0 per spec."""
        from apoch.public_api.models import EvidenceSource

        source = EvidenceSource("Guardian", 0.5, 10, "diagnostics")
        assert isinstance(source.confidence, float)
        assert 0.0 <= source.confidence <= 1.0

    def test_to_dict_roundtrip(self):
        """EvidenceSource serializes to dict and back preserving all fields."""
        from apoch.public_api.models import EvidenceSource

        original = EvidenceSource("Vision", 0.9, 5, "module state")
        d = original.to_dict()
        expected = {
            "source": "Vision",
            "confidence": 0.9,
            "collected_ago": 5,
            "based_on": "module state",
        }
        assert d == expected

        restored = EvidenceSource.from_dict(d)
        assert restored.source == original.source
        assert restored.confidence == original.confidence
        assert restored.collected_ago == original.collected_ago
        assert restored.based_on == original.based_on

    def test_from_dict_with_extra_keys(self):
        """from_dict ignores extra keys gracefully."""
        from apoch.public_api.models import EvidenceSource

        d = {
            "source": "Test",
            "confidence": 0.5,
            "collected_ago": 1,
            "based_on": "x",
            "extra": "ignored",
        }
        source = EvidenceSource.from_dict(d)
        assert source.source == "Test"
        assert source.confidence == 0.5

    def test_from_dict_missing_field_raises(self):
        """from_dict raises KeyError when a required field is missing."""
        from apoch.public_api.models import EvidenceSource

        with pytest.raises(KeyError):
            EvidenceSource.from_dict({"source": "Test", "confidence": 0.5, "collected_ago": 1})


class TestToolResponse:
    """ToolResponse dataclass construction and serialization."""

    def test_construction_with_minimal_fields(self):
        """ToolResponse can be created with only required fields."""
        from apoch.public_api.models import EvidenceSource, ToolResponse

        response = ToolResponse(
            summary="System is running",
            explanation="All modules active",
            evidence=[EvidenceSource("Vision", 0.9, 5, "module state")],
        )

        assert response.api_version == "1.0"
        assert response.summary == "System is running"
        assert response.explanation == "All modules active"
        assert response.confidence == 0.0  # default
        assert len(response.evidence) == 1
        assert response.suggested_action is None
        assert response.metadata == {}

    def test_construction_with_all_fields(self):
        """ToolResponse stores every field correctly."""
        from apoch.public_api.models import EvidenceSource, ToolResponse

        ts = datetime.now(UTC).isoformat()
        response = ToolResponse(
            api_version="1.0",
            summary="test",
            explanation="test explanation",
            evidence=[
                EvidenceSource("Vision", 0.9, 5, "module"),
                EvidenceSource("Guardian", 0.8, 10, "diagnostics"),
            ],
            suggested_action="Check logs",
            confidence=0.85,
            generated_at=ts,
            data_freshness=30,
            metadata={"key": "value"},
        )

        assert response.api_version == "1.0"
        assert response.summary == "test"
        assert response.explanation == "test explanation"
        assert len(response.evidence) == 2
        assert response.suggested_action == "Check logs"
        assert response.confidence == 0.85
        assert response.generated_at == ts
        assert response.data_freshness == 30
        assert response.metadata == {"key": "value"}

    def test_to_dict_roundtrip(self):
        """Serialization to dict and back preserves all fields."""
        from apoch.public_api.models import EvidenceSource, ToolResponse

        original = ToolResponse(
            summary="System OK",
            explanation="All good",
            evidence=[EvidenceSource("Vision", 0.9, 5, "module state")],
            suggested_action="None",
            confidence=0.9,
            generated_at="2026-07-16T12:00:00+00:00",
            data_freshness=5,
            metadata={"test": True},
        )

        d = original.to_dict()
        assert d["api_version"] == "1.0"
        assert d["summary"] == "System OK"
        assert d["confidence"] == 0.9
        assert len(d["evidence"]) == 1
        assert d["evidence"][0]["source"] == "Vision"

        restored = ToolResponse.from_dict(d)
        assert restored.summary == original.summary
        assert restored.confidence == original.confidence
        assert restored.suggested_action == original.suggested_action
        assert restored.metadata == original.metadata
        assert len(restored.evidence) == 1
        assert restored.evidence[0].source == "Vision"

    def test_to_dict_includes_api_version_first(self):
        """api_version is the first field in the serialized dict."""
        from apoch.public_api.models import EvidenceSource, ToolResponse

        response = ToolResponse(
            summary="test",
            explanation="test",
            evidence=[EvidenceSource("X", 0.5, 1, "test")],
        )
        d = response.to_dict()
        keys = list(d.keys())
        assert keys[0] == "api_version", f"Expected api_version first, got {keys}"

    def test_from_dict_with_extra_keys(self):
        """from_dict ignores extra keys gracefully."""
        from apoch.public_api.models import ToolResponse

        d = {
            "api_version": "1.0",
            "summary": "test",
            "explanation": "test",
            "evidence": [
                {"source": "X", "confidence": 0.5, "collected_ago": 1, "based_on": "test"},
            ],
            "suggested_action": None,
            "confidence": 0.5,
            "generated_at": "",
            "data_freshness": 0,
            "metadata": {},
            "extra_key": "should_be_ignored",
        }
        restored = ToolResponse.from_dict(d)
        assert restored.summary == "test"

    def test_from_dict_missing_required_field_raises(self):
        """from_dict raises KeyError when a required field is missing."""
        from apoch.public_api.models import ToolResponse

        with pytest.raises(KeyError):
            ToolResponse.from_dict(
                {
                    "api_version": "1.0",
                    "summary": "test",
                    # missing explanation, evidence
                }
            )


class TestRecommendResponse:
    """RecommendResponse extends ToolResponse with priority and expected_benefit."""

    def test_is_subclass_of_tool_response(self):
        """RecommendResponse inherits from ToolResponse."""
        from apoch.public_api.models import RecommendResponse, ToolResponse

        assert issubclass(RecommendResponse, ToolResponse)

    def test_construction_with_all_fields(self):
        """RecommendResponse stores all ToolResponse fields plus its own."""
        from apoch.public_api.models import EvidenceSource, RecommendResponse

        response = RecommendResponse(
            summary="Fix module",
            explanation="Guardian needs attention",
            evidence=[EvidenceSource("Guardian", 0.8, 10, "diagnostics")],
            suggested_action="Restart module",
            confidence=0.8,
            generated_at="2026-07-16T12:00:00+00:00",
            data_freshness=10,
            priority="HIGH",
            expected_benefit="Restores system stability",
        )

        assert response.priority == "HIGH"
        assert response.expected_benefit == "Restores system stability"
        assert response.summary == "Fix module"
        assert response.confidence == 0.8

    def test_priority_default(self):
        """priority defaults to MEDIUM."""
        from apoch.public_api.models import EvidenceSource, RecommendResponse

        response = RecommendResponse(
            summary="test",
            explanation="test",
            evidence=[EvidenceSource("X", 0.5, 1, "test")],
        )
        assert response.priority == "MEDIUM"

    def test_expected_benefit_default(self):
        """expected_benefit defaults to None."""
        from apoch.public_api.models import EvidenceSource, RecommendResponse

        response = RecommendResponse(
            summary="test",
            explanation="test",
            evidence=[EvidenceSource("X", 0.5, 1, "test")],
        )
        assert response.expected_benefit is None

    def test_to_dict_roundtrip(self):
        """RecommendResponse serializes with extra fields and restores correctly."""
        from apoch.public_api.models import EvidenceSource, RecommendResponse

        original = RecommendResponse(
            summary="Optimize",
            explanation="Performance gain",
            evidence=[EvidenceSource("Optimizer", 0.7, 20, "hypotheses")],
            suggested_action="Apply config change",
            confidence=0.7,
            generated_at="2026-07-16T12:00:00+00:00",
            data_freshness=20,
            priority="HIGH",
            expected_benefit="15% latency reduction",
        )

        d = original.to_dict()
        assert d["priority"] == "HIGH"
        assert d["expected_benefit"] == "15% latency reduction"

        restored = RecommendResponse.from_dict(d)
        assert restored.priority == "HIGH"
        assert restored.expected_benefit == "15% latency reduction"
        assert restored.summary == "Optimize"

    def test_from_dict_creates_recommend_response(self):
        """from_dict with priority/expected_benefit returns RecommendResponse."""
        from apoch.public_api.models import RecommendResponse

        d = {
            "api_version": "1.0",
            "summary": "test",
            "explanation": "test",
            "evidence": [
                {"source": "X", "confidence": 0.5, "collected_ago": 1, "based_on": "test"},
            ],
            "suggested_action": None,
            "confidence": 0.5,
            "generated_at": "",
            "data_freshness": 0,
            "metadata": {},
            "priority": "LOW",
            "expected_benefit": None,
        }
        restored = RecommendResponse.from_dict(d)
        assert isinstance(restored, RecommendResponse)
        assert restored.priority == "LOW"


class TestErrorResponse:
    """ErrorResponse dataclass for error envelopes."""

    def test_defaults_ok_false(self):
        """ErrorResponse defaults to ok=False."""
        from apoch.public_api.models import ErrorResponse

        err = ErrorResponse()
        assert err.ok is False

    def test_error_dict_defaults_to_empty(self):
        """ErrorResponse error defaults to empty dict."""
        from apoch.public_api.models import ErrorResponse

        err = ErrorResponse()
        assert err.error == {}

    def test_with_error_dict(self):
        """ErrorResponse stores error dict with code and message."""
        from apoch.public_api.models import ErrorResponse

        err = ErrorResponse(error={"code": "ERR_TIMEOUT", "message": "Module did not respond"})
        assert err.ok is False
        assert err.error["code"] == "ERR_TIMEOUT"
        assert "did not respond" in err.error["message"]

    def test_to_dict_roundtrip(self):
        """ErrorResponse serializes to dict and back."""
        from apoch.public_api.models import ErrorResponse

        original = ErrorResponse(error={"code": "ERR_NO_DATA", "message": "No data available"})
        d = original.to_dict()
        assert d == {"ok": False, "error": {"code": "ERR_NO_DATA", "message": "No data available"}}

        restored = ErrorResponse.from_dict(d)
        assert restored.ok is False
        assert restored.error["code"] == "ERR_NO_DATA"
