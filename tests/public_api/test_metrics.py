"""Tests for CallMetrics dataclass (RED phase: class doesn't exist yet).

Design: ADR-Metrics (CallMetrics dataclass)
Design: §Métricas Internas del Coordinador
"""

from datetime import UTC, datetime


class TestCallMetrics:
    """CallMetrics dataclass construction and field types."""

    def test_construction_with_all_fields(self):
        """CallMetrics stores all provided fields correctly."""
        from apoch.public_api.metrics import CallMetrics

        ts = datetime.now(UTC).isoformat()
        metrics = CallMetrics(
            tool="apoch_status",
            modules_consulted=["vision", "guardian", "chronicle"],
            modules_succeeded=["vision", "chronicle"],
            modules_failed=["guardian"],
            time_per_module={"vision": 0.1, "guardian": 0.5, "chronicle": 0.2},
            total_time=0.8,
            confidence_final=0.66,
            evidence_count=2,
            timestamp=ts,
        )

        assert metrics.tool == "apoch_status"
        assert metrics.modules_consulted == ["vision", "guardian", "chronicle"]
        assert metrics.modules_succeeded == ["vision", "chronicle"]
        assert metrics.modules_failed == ["guardian"]
        assert metrics.time_per_module == {"vision": 0.1, "guardian": 0.5, "chronicle": 0.2}
        assert metrics.total_time == 0.8
        assert metrics.confidence_final == 0.66
        assert metrics.evidence_count == 2
        assert metrics.timestamp == ts
        assert metrics.error_code is None  # default

    def test_construction_with_error_code(self):
        """CallMetrics can be constructed with an error_code."""
        from apoch.public_api.metrics import CallMetrics

        metrics = CallMetrics(
            tool="apoch_status",
            modules_consulted=["vision"],
            modules_succeeded=[],
            modules_failed=["vision"],
            time_per_module={"vision": 1.0},
            total_time=1.0,
            confidence_final=0.0,
            evidence_count=0,
            timestamp="2026-07-16T12:00:00+00:00",
            error_code="ERR_TIMEOUT",
        )
        assert metrics.error_code == "ERR_TIMEOUT"

    def test_field_types(self):
        """Each field has the expected Python type."""
        from apoch.public_api.metrics import CallMetrics

        metrics = CallMetrics(
            tool="test",
            modules_consulted=["a", "b"],
            modules_succeeded=["a"],
            modules_failed=["b"],
            time_per_module={"a": 0.1},
            total_time=0.1,
            confidence_final=0.5,
            evidence_count=1,
            timestamp="now",
        )

        assert isinstance(metrics.tool, str)
        assert isinstance(metrics.modules_consulted, list)
        assert isinstance(metrics.modules_succeeded, list)
        assert isinstance(metrics.modules_failed, list)
        assert isinstance(metrics.time_per_module, dict)
        assert isinstance(metrics.total_time, (int, float))
        assert isinstance(metrics.confidence_final, (int, float))
        assert isinstance(metrics.evidence_count, int)
        assert isinstance(metrics.timestamp, str)
        assert metrics.error_code is None or isinstance(metrics.error_code, str)

    def test_empty_lists_allowed(self):
        """Modules consulted/succeeded/failed can be empty lists."""
        from apoch.public_api.metrics import CallMetrics

        metrics = CallMetrics(
            tool="test",
            modules_consulted=[],
            modules_succeeded=[],
            modules_failed=[],
            time_per_module={},
            total_time=0.0,
            confidence_final=0.0,
            evidence_count=0,
            timestamp="now",
        )
        assert metrics.modules_consulted == []
        assert metrics.modules_succeeded == []
        assert metrics.modules_failed == []
