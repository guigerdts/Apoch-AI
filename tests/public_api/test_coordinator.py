"""Tests for ApochCoordinator (RED phase: class doesn't exist yet).

Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)
Spec: mcp-public-api §Catálogo Global de Códigos de Error, §Niveles de Confianza
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

import asyncio

import pytest


@pytest.fixture
def sample_registry():
    """Build a ServiceRegistry with mock services for testing."""
    from apoch.public_api.registry import ServiceRegistry

    registry = ServiceRegistry()
    registry.vision = _MockService("vision_data")
    registry.guardian = _MockService("guardian_data")
    registry.chronicle = _MockService("chronicle_data")
    registry.oracle = _MockService("oracle_data")
    return registry


@pytest.fixture
def partial_registry():
    """Registry with some None services (not loaded)."""
    from apoch.public_api.registry import ServiceRegistry

    registry = ServiceRegistry()
    registry.vision = _MockService("vision_data")
    registry.guardian = None  # not loaded
    registry.pulse = _MockService("pulse_data")
    return registry


class _MockService:
    """Minimal mock that returns fixed data."""

    def __init__(self, data: str) -> None:
        self._data = data

    async def fetch(self) -> str:
        return self._data


class _SlowService:
    """Mock that sleeps beyond timeout."""

    async def fetch(self) -> str:
        await asyncio.sleep(10)
        return "too_late"


class _FailingService:
    """Mock that raises."""

    async def fetch(self) -> str:
        msg = "internal failure"
        raise RuntimeError(msg)


class TestQueryModules:
    """_query_modules() — parallel execution with per-module timeouts."""

    async def test_all_modules_respond(self, sample_registry):
        """All queried modules return data within timeout."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(sample_registry)

        results = await coordinator._query_modules([
            ("vision", sample_registry.vision.fetch(), 1.0),
            ("guardian", sample_registry.guardian.fetch(), 1.0),
        ])

        assert results["vision"] == "vision_data"
        assert results["guardian"] == "guardian_data"
        assert len(results) == 2

    async def test_timeout_returns_none_in_results(self):
        """A module that times out gets None in results; others respond."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _SlowService()
        registry.guardian = _MockService("guardian_data")

        coordinator = ApochCoordinator(registry)

        results = await coordinator._query_modules([
            ("vision", registry.vision.fetch(), 0.05),
            ("guardian", registry.guardian.fetch(), 1.0),
        ])

        assert results["vision"] is None  # timed out
        assert results["guardian"] == "guardian_data"

    async def test_exception_returns_none_in_results(self):
        """A module that raises gets None; others still respond."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _FailingService()
        registry.guardian = _MockService("guardian_data")

        coordinator = ApochCoordinator(registry)

        results = await coordinator._query_modules([
            ("vision", registry.vision.fetch(), 1.0),
            ("guardian", registry.guardian.fetch(), 1.0),
        ])

        assert results["vision"] is None  # exception
        assert results["guardian"] == "guardian_data"

    async def test_mixed_timeout_and_data(self):
        """Mix of timeout and data produces correct results."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.guardian = _MockService("guardian_data")
        registry.chronicle = _SlowService()  # will timeout

        coordinator = ApochCoordinator(registry)

        results = await coordinator._query_modules([
            ("guardian", registry.guardian.fetch(), 1.0),
            ("chronicle", registry.chronicle.fetch(), 0.05),
        ])

        assert results["guardian"] == "guardian_data"
        assert results["chronicle"] is None

    async def test_no_timeout_does_not_propagate(self):
        """A single module timeout does NOT cancel other modules."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _SlowService()
        registry.guardian = _MockService("guardian_data")

        coordinator = ApochCoordinator(registry)

        results = await coordinator._query_modules([
            ("vision", registry.vision.fetch(), 0.05),
            ("guardian", registry.guardian.fetch(), 1.0),
        ])

        # Guardian must still have its data
        assert results["guardian"] == "guardian_data"
        # Vision must be None (timed out)
        assert results["vision"] is None


class TestCalculateConfidence:
    """_calculate_confidence() weighted average of available sources."""

    def test_all_available(self):
        """All queried modules responded → confidence = 1.0."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": "data", "guardian": "data", "chronicle": "data"}
        assert coordinator._calculate_confidence(results) == 1.0

    def test_half_available(self):
        """Half the modules responded → confidence = 0.5."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": "data", "guardian": None, "chronicle": "data", "oracle": None}
        assert coordinator._calculate_confidence(results) == 0.5

    def test_none_available(self):
        """No modules responded → confidence = 0.0."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": None, "guardian": None}
        assert coordinator._calculate_confidence(results) == 0.0

    def test_empty_results(self):
        """No modules queried → confidence = 0.0."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert coordinator._calculate_confidence({}) == 0.0

    def test_one_of_three(self):
        """One of three responded → confidence = 0.33."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"a": "data", "b": None, "c": None}
        assert coordinator._calculate_confidence(results) == pytest.approx(0.33, abs=0.01)


class TestConfidenceLabel:
    """_confidence_label() maps float to string label."""

    def test_very_high(self):
        from apoch.public_api.coordinator import ApochCoordinator

        assert ApochCoordinator._confidence_label(0.95) == "VERY_HIGH"
        assert ApochCoordinator._confidence_label(0.90) == "VERY_HIGH"

    def test_high(self):
        from apoch.public_api.coordinator import ApochCoordinator

        assert ApochCoordinator._confidence_label(0.80) == "HIGH"
        assert ApochCoordinator._confidence_label(0.75) == "HIGH"

    def test_medium(self):
        from apoch.public_api.coordinator import ApochCoordinator

        assert ApochCoordinator._confidence_label(0.60) == "MEDIUM"
        assert ApochCoordinator._confidence_label(0.50) == "MEDIUM"

    def test_low(self):
        from apoch.public_api.coordinator import ApochCoordinator

        assert ApochCoordinator._confidence_label(0.35) == "LOW"
        assert ApochCoordinator._confidence_label(0.25) == "LOW"

    def test_very_low(self):
        from apoch.public_api.coordinator import ApochCoordinator

        assert ApochCoordinator._confidence_label(0.10) == "VERY_LOW"
        assert ApochCoordinator._confidence_label(0.0) == "VERY_LOW"


class TestBuildEvidence:
    """_build_evidence() creates EvidenceSource list from results."""

    def test_all_available(self):
        """Non-None results produce one EvidenceSource each."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": {"state": "ok"}, "guardian": {"healthy": True}}

        evidence = coordinator._build_evidence(results)
        assert len(evidence) == 2
        sources = {e.source for e in evidence}
        assert "Vision" in sources
        assert "Guardian" in sources

    def test_skips_none_results(self):
        """None values are filtered out of evidence."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": {"state": "ok"}, "guardian": None, "chronicle": None}

        evidence = coordinator._build_evidence(results)
        assert len(evidence) == 1
        assert evidence[0].source == "Vision"

    def test_empty_results(self):
        """No results → empty evidence list."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert coordinator._build_evidence({}) == []


class TestBuildResponse:
    """_build_success_response() and _build_error_response()."""

    def test_success_response_contains_all_fields(self):
        """Success response has every expected field."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": {"state": "ok"}}

        response = coordinator._build_success_response(
            results=results,
            summary="System running",
            explanation="All modules active",
            suggested_action="None",
        )

        assert response["api_version"] == "1.0"
        assert response["summary"] == "System running"
        assert response["explanation"] == "All modules active"
        assert response["confidence"] == 1.0
        assert isinstance(response["evidence"], list)
        assert len(response["evidence"]) == 1
        assert "generated_at" in response
        assert "data_freshness" in response
        assert response["metadata"] == {}

    def test_success_response_with_partial_evidence(self):
        """Partial evidence yields lower confidence."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        results = {"vision": {"state": "ok"}, "guardian": None, "chronicle": {"events": []}}

        response = coordinator._build_success_response(
            results=results,
            summary="Partial data",
            explanation="Some modules unavailable",
        )

        assert response["confidence"] == pytest.approx(0.67, abs=0.01)
        assert len(response["evidence"]) == 2

    def test_error_response_format(self):
        """Error response follows catalog format."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())

        error = coordinator._build_error_response("ERR_TIMEOUT", "All modules timed out")
        assert error["ok"] is False
        assert error["error"]["code"] == "ERR_TIMEOUT"
        assert "timed out" in error["error"]["message"]

    def test_error_response_not_implemented(self):
        """ERR_NOT_IMPLEMENTED error format."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())

        error = coordinator._build_error_response("ERR_NOT_IMPLEMENTED", "Not implemented yet")
        assert error["ok"] is False
        assert error["error"]["code"] == "ERR_NOT_IMPLEMENTED"


class TestToolStubs:
    """5 remaining tool methods return ERR_NOT_IMPLEMENTED (status+health done)."""

    @pytest.fixture
    def coordinator(self):
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        return ApochCoordinator(ServiceRegistry())

    async def test_status_empty_registry(self, coordinator):
        """status() with empty registry → ERR_TIMEOUT (no modules to query)."""
        result = await coordinator.status()
        assert result["ok"] is False
        # With an empty ServiceRegistry, no modules are queried → ERR_TIMEOUT
        assert result["error"]["code"] == "ERR_TIMEOUT"
        assert "No modules responded" in result["error"]["message"]

    async def test_history_not_implemented(self, coordinator):
        result = await coordinator.history()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_recommend_not_implemented(self, coordinator):
        result = await coordinator.recommend()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_progress_not_implemented(self, coordinator):
        result = await coordinator.progress()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_insights_not_implemented(self, coordinator):
        result = await coordinator.insights()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_logs_not_implemented(self, coordinator):
        result = await coordinator.logs()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"


class TestCoordinatorConstruction:
    """ApochCoordinator construction and defaults."""

    def test_requires_services(self):
        """Coordinator requires a ServiceRegistry."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert coordinator._services is not None

    def test_default_timeouts_configured(self):
        """Coordinator has default timeouts for all 6 modules."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert "vision" in coordinator._timeouts
        assert "guardian" in coordinator._timeouts
        assert "chronicle" in coordinator._timeouts
        assert "oracle" in coordinator._timeouts
        assert "pulse" in coordinator._timeouts
        assert "optimizer" in coordinator._timeouts

    def test_timeouts_are_positive(self):
        """All timeout values are positive floats."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        for timeout in coordinator._timeouts.values():
            assert isinstance(timeout, float)
            assert timeout > 0
