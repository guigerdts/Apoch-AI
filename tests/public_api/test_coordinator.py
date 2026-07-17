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

    async def test_history_empty_registry(self, coordinator):
        """history() with empty registry → ERR_DEPENDENCY_UNAVAILABLE (no Chronicle)."""
        result = await coordinator.history()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_recommend_empty_registry(self, coordinator):
        """Empty registry → recommend sees no sources → ERR_TIMEOUT."""
        result = await coordinator.recommend()
        # Empty registry means no modules to query → no data
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"

    async def test_progress_is_implemented(self, coordinator):
        result = await coordinator.progress()
        # Empty registry → pulse None → ERR_DEPENDENCY_UNAVAILABLE (not ERR_NOT_IMPLEMENTED)
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_insights_is_implemented(self, coordinator):
        result = await coordinator.insights()
        # Empty registry → optimizer None → ERR_DEPENDENCY_UNAVAILABLE (not ERR_NOT_IMPLEMENTED)
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_logs_is_implemented(self, coordinator):
        result = await coordinator.logs()
        # Empty registry → vision None → ERR_DEPENDENCY_UNAVAILABLE (not ERR_NOT_IMPLEMENTED)
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"


class TestLogs:
    """apoch_logs tool — full implementation tests.

    Spec: mcp-public-api §Tool 7: apoch_logs
    Design: coordinator.logs() docstring
    Tasks: PR8 — all documented test cases
    """

    @pytest.fixture
    def vision_log_registry(self):
        """Registry with Vision that returns sample LogRecords."""
        from datetime import UTC, datetime

        from apoch.modules.vision.models import LogRecord
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _VisionWithLogs([
            LogRecord(
                timestamp=datetime(2026, 7, 17, 10, 0, 0, tzinfo=UTC),
                level="INFO",
                message="Sistema iniciado",
                module="core",
                pid=1001,
                context={"version": "1.0"},
            ),
            LogRecord(
                timestamp=datetime(2026, 7, 17, 10, 1, 0, tzinfo=UTC),
                level="ERROR",
                message="Conexión fallida",
                module="optimizer",
                pid=1001,
                context={"retry_count": 3},
            ),
            LogRecord(
                timestamp=datetime(2026, 7, 17, 10, 2, 0, tzinfo=UTC),
                level="WARN",
                message="Latencia alta",
                module="pulse",
                pid=1001,
                context={"latency_ms": 5000},
            ),
            LogRecord(
                timestamp=datetime(2026, 7, 17, 10, 3, 0, tzinfo=UTC),
                level="INFO",
                message="Health check OK",
                module="core",
                pid=1001,
                context={},
            ),
            LogRecord(
                timestamp=datetime(2026, 7, 17, 10, 4, 0, tzinfo=UTC),
                level="ERROR",
                message="Timeout en Vision",
                module="vision",
                pid=1002,
                context={"timeout_s": 0.5},
            ),
        ])
        return registry

    @pytest.fixture
    def vision_empty_registry(self):
        """Registry with Vision that returns empty list."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _VisionWithLogs([])
        return registry

    @pytest.fixture
    def vision_timeout_registry(self):
        """Registry with Vision that times out."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = _VisionTimeout()
        return registry

    @pytest.fixture
    def vision_none_registry(self):
        """Registry with Vision=None (not loaded)."""
        from apoch.public_api.registry import ServiceRegistry

        registry = ServiceRegistry()
        registry.vision = None
        return registry

    # ── Happy path ─────────────────────────────────────────────────────

    async def test_happy_path_all_logs(self, vision_log_registry):
        """Returns all logs when no filters are applied."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs()

        assert result["confidence"] == 1.0
        assert result["suggested_action"] is None
        assert "5 entradas de log" in result["summary"]
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["source"] == "Sistema de monitoreo"

    async def test_happy_path_output_format(self, vision_log_registry):
        """Each log line has the correct format: [ts] LEVEL [module] — message."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs()

        lines = result["explanation"].split("\n")
        assert len(lines) == 5

        # Each line: [ISO timestamp] LEVEL [module] — message
        for line in lines:
            assert line.startswith("[")
            assert "] " in line
            assert " — " in line

        # First line: [2026-07-17T10:00:00+00:00] INFO [core] — Sistema iniciado
        assert "INFO" in lines[0]
        assert "[core]" in lines[0]
        assert "Sistema iniciado" in lines[0]

        # Second line: ERROR entry
        assert "ERROR" in lines[1]
        assert "[optimizer]" in lines[1]
        assert "Conexión fallida" in lines[1]

    # ── Filter by nivel ────────────────────────────────────────────────

    async def test_filter_by_nivel(self, vision_log_registry):
        """Filtering by level returns only matching entries."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(nivel="ERROR")

        lines = result["explanation"].split("\n")
        assert len(lines) == 2  # 2 ERROR entries
        assert all("ERROR" in line for line in lines)

    async def test_filter_by_nivel_case_insensitive(self, vision_log_registry):
        """Level filter is case-insensitive."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(nivel="error")

        lines = result["explanation"].split("\n")
        assert len(lines) == 2

    # ── Filter by modulo ───────────────────────────────────────────────

    async def test_filter_by_modulo(self, vision_log_registry):
        """Filtering by module returns only matching entries (in-memory)."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(modulo="core")

        lines = result["explanation"].split("\n")
        assert len(lines) == 2  # 2 core entries
        assert all("[core]" in line for line in lines)

    # ── Modulo + limite simultaneously ─────────────────────────────────

    async def test_modulo_plus_limite(self, vision_log_registry):
        """When modulo + limite are used, limite applies AFTER module filter."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        # 2 core entries, limit 1 → should get 1
        result = await coordinator.logs(modulo="core", limite=1)

        lines = result["explanation"].split("\n")
        assert len(lines) == 1
        assert "[core]" in lines[0]

    # ── Limite ─────────────────────────────────────────────────────────

    async def test_limite(self, vision_log_registry):
        """Limit caps the number of returned entries."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(limite=2)

        lines = result["explanation"].split("\n")
        assert len(lines) == 2

    # ── No results ─────────────────────────────────────────────────────

    async def test_no_results_empty_response(self, vision_empty_registry):
        """Empty results produce confidence 0.3 and no-data message."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_empty_registry)
        result = await coordinator.logs()

        assert result["confidence"] == 0.3
        assert "No hay entradas de log" in result["summary"]

    # ── Confidence ─────────────────────────────────────────────────────

    async def test_confidence_with_data(self, vision_log_registry):
        """Confidence is 1.0 when Vision returns data."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs()
        assert result["confidence"] == 1.0

    async def test_confidence_empty(self, vision_empty_registry):
        """Confidence is 0.3 when Vision returns empty list."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_empty_registry)
        result = await coordinator.logs()
        assert result["confidence"] == 0.3

    # ── Output contract (P6: no context/pid) ───────────────────────────

    async def test_no_context_or_pid_in_output(self, vision_log_registry):
        """Output NEVER contains context, pid, or LogRecord structures."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs()

        explanation = result["explanation"]
        # Should NOT contain raw context, pid, or dict representations
        assert "context" not in explanation
        assert "pid" not in explanation
        assert "retry_count" not in explanation  # from LogRecord.context
        assert "1001" not in explanation  # pid should not be exposed
        assert "LogRecord" not in explanation
        assert "{" not in explanation  # no raw dicts

    # ── Invalid params ─────────────────────────────────────────────────

    async def test_invalid_nivel(self, vision_log_registry):
        """Invalid level → ERR_INVALID_ARGUMENT."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(nivel="DEBUG")

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_invalid_limite_zero(self, vision_log_registry):
        """Limite=0 → ERR_INVALID_ARGUMENT."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(limite=0)

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_invalid_limite_negative(self, vision_log_registry):
        """Limite negative → ERR_INVALID_ARGUMENT."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs(limite=-5)

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    # ── Vision timeout ─────────────────────────────────────────────────

    async def test_vision_timeout(self, vision_timeout_registry):
        """Vision timeout → ERR_DEPENDENCY_UNAVAILABLE."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_timeout_registry)
        result = await coordinator.logs()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    # ── Vision not available ───────────────────────────────────────────

    async def test_vision_not_available(self, vision_none_registry):
        """Vision not loaded → ERR_DEPENDENCY_UNAVAILABLE."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_none_registry)
        result = await coordinator.logs()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    # ── Tool registration ─────────────────────────────────────────────

    async def test_tool_def_registration(self):
        """get_tool_defs() includes apoch_logs (7 tools total)."""
        from apoch.public_api.coordinator import ApochCoordinator

        tools = ApochCoordinator.get_tool_defs()
        names = [t.name for t in tools]
        assert "apoch_logs" in names
        assert len(names) == 7  # PR8: 7 public tools

    async def test_tool_def_schema(self):
        """apoch_logs ToolDef has correct schema."""
        from apoch.public_api.coordinator import ApochCoordinator

        tools = ApochCoordinator.get_tool_defs()
        logs_def = next(t for t in tools if t.name == "apoch_logs")
        assert logs_def.handler_name == "logs"
        assert "nivel" in logs_def.input_schema["properties"]
        assert logs_def.input_schema["properties"]["nivel"]["enum"] == [
            "INFO", "WARN", "ERROR", "FATAL",
        ]
        assert "limite" in logs_def.input_schema["properties"]
        assert "modulo" in logs_def.input_schema["properties"]

    # ── suggested_action ──────────────────────────────────────────────

    async def test_suggested_action_is_none(self, vision_log_registry):
        """suggested_action is always None."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_log_registry)
        result = await coordinator.logs()
        assert result["suggested_action"] is None

    async def test_suggested_action_none_empty(self, vision_empty_registry):
        """suggested_action is None even when empty."""
        from apoch.public_api.coordinator import ApochCoordinator

        coordinator = ApochCoordinator(vision_empty_registry)
        result = await coordinator.logs()
        assert result["suggested_action"] is None


class _VisionWithLogs:
    """Mock Vision module that returns predefined LogRecord list."""

    def __init__(self, logs: list) -> None:
        self._logs = logs

    async def recent(self, limit: int = 50, level: str | None = None) -> list:
        """Simulate Vision.recent() with optional level filter."""
        from copy import deepcopy

        entries = deepcopy(self._logs)
        if level is not None:
            entries = [e for e in entries if e.level.upper() == level.upper()]
        return entries[:limit]


class _VisionTimeout:
    """Mock Vision module that times out."""

    async def recent(self, limit: int = 50, level: str | None = None) -> list:
        """Simulate a Vision timeout."""
        await asyncio.sleep(10)
        return []


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


class TestLegacyAliases:
    """PR9 — legacy aliases delegate to public tools with deprecation metadata.

    Spec: mcp-public-api §Plan de Migración
    Design: ADR-006 — Fase 1+2 (alias directo + deprecación)
    """

    @pytest.fixture
    def coordinator(self):
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        return ApochCoordinator(ServiceRegistry())

    # ── Registration ─────────────────────────────────────────────────

    def test_get_legacy_aliases_exists(self):
        """get_legacy_aliases() classmethod exists and returns list."""
        from apoch.public_api.coordinator import ApochCoordinator

        aliases = ApochCoordinator.get_legacy_aliases()
        assert isinstance(aliases, list)
        assert len(aliases) == 5

    def test_get_legacy_aliases_has_expected_names(self):
        """Each legacy alias has the expected name."""
        from apoch.public_api.coordinator import ApochCoordinator

        names = {a.name for a in ApochCoordinator.get_legacy_aliases()}
        assert names == {
            "vision_state",
            "chronicle_query",
            "guardian_diagnostics",
            "guardian_all_diagnostics",
            "vision_logs",
        }

    def test_each_alias_has_deprecated_description(self):
        """Each legacy alias description contains [DEPRECATED]."""
        from apoch.public_api.coordinator import ApochCoordinator

        for alias in ApochCoordinator.get_legacy_aliases():
            assert "[DEPRECATED]" in alias.description, (
                f"Alias '{alias.name}' missing [DEPRECATED] tag"
            )

    def test_each_alias_handler_is_legacy_method(self):
        """Each alias handler_name starts with 'legacy_'."""
        from apoch.public_api.coordinator import ApochCoordinator

        for alias in ApochCoordinator.get_legacy_aliases():
            assert alias.handler_name.startswith("legacy_"), (
                f"Alias '{alias.name}' handler '{alias.handler_name}' "
                f"does not start with 'legacy_'"
            )

    def test_legacy_handlers_exist_on_coordinator(self):
        """Each legacy_* handler is a callable method on the coordinator."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        for alias in ApochCoordinator.get_legacy_aliases():
            handler = getattr(coordinator, alias.handler_name, None)
            assert handler is not None, (
                f"Handler '{alias.handler_name}' not found"
            )
            assert callable(handler)

    # ── Delegation: each alias → public tool ─────────────────────────
    #
    # The coordinator has no registered modules, so all public tools
    # return error responses. The tests verify delegation happened
    # (metadata injection) and the error code matches the public tool.

    async def test_legacy_vision_state_delegates_to_status(self, coordinator):
        """vision_state calls status() and adds metadata (ERR_TIMEOUT)."""
        result = await coordinator.legacy_vision_state()
        assert result["metadata"]["legacy_tool"] == "vision_state"
        assert result["metadata"]["replaced_by"] == "apoch_status"
        assert result["metadata"]["deprecated_since"] == "1.0"
        assert result.get("error", {}).get("code") == "ERR_TIMEOUT"

    async def test_legacy_vision_state_accepts_module_param(self, coordinator):
        """vision_state accepts (and ignores) module param."""
        result = await coordinator.legacy_vision_state(module="vision")
        assert result["metadata"]["legacy_tool"] == "vision_state"
        assert "error" in result  # empty registry — error expected

    async def test_legacy_guardian_diagnostics_delegates_to_health(self, coordinator):
        """guardian_diagnostics calls health() and adds metadata (ERR_DEPENDENCY_UNAVAILABLE)."""
        result = await coordinator.legacy_guardian_diagnostics(
            module_name="test",
        )
        assert result["metadata"]["legacy_tool"] == "guardian_diagnostics"
        assert result["metadata"]["replaced_by"] == "apoch_health"
        assert result.get("error", {}).get("code") == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_legacy_guardian_all_diagnostics_delegates_to_health(
        self, coordinator
    ):
        """guardian_all_diagnostics calls health() and adds metadata."""
        result = await coordinator.legacy_guardian_all_diagnostics()
        assert result["metadata"]["legacy_tool"] == "guardian_all_diagnostics"
        assert result["metadata"]["replaced_by"] == "apoch_health"
        assert result.get("error", {}).get("code") == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_legacy_chronicle_query_delegates_to_history(
        self, coordinator
    ):
        """chronicle_query calls history() and adds metadata (ERR_DEPENDENCY_UNAVAILABLE)."""
        result = await coordinator.legacy_chronicle_query()
        assert result["metadata"]["legacy_tool"] == "chronicle_query"
        assert result["metadata"]["replaced_by"] == "apoch_history"
        assert result.get("error", {}).get("code") == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_legacy_chronicle_query_maps_since_to_hours(
        self, coordinator
    ):
        """chronicle_query since param converts to horas (ERR_DEPENDENCY_UNAVAILABLE)."""
        from datetime import UTC, datetime, timedelta

        two_hours_ago = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        result = await coordinator.legacy_chronicle_query(since=two_hours_ago)
        assert result["metadata"]["legacy_tool"] == "chronicle_query"
        assert result.get("error", {}).get("code") == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_legacy_chronicle_query_maps_event_type(
        self, coordinator
    ):
        """chronicle_query event_type maps to tipo (ERR_DEPENDENCY_UNAVAILABLE)."""
        result = await coordinator.legacy_chronicle_query(
            event_type="tool_call",
        )
        assert result["metadata"]["legacy_tool"] == "chronicle_query"
        assert result.get("error", {}).get("code") == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_legacy_vision_logs_delegates_to_logs(self, coordinator):
        """vision_logs delegates to logs() — empty registry → ERR_DEPENDENCY_UNAVAILABLE."""
        result = await coordinator.legacy_vision_logs()
        assert result["ok"] is False
        assert result["metadata"]["legacy_tool"] == "vision_logs"
        assert result["metadata"]["replaced_by"] == "apoch_logs"

    async def test_legacy_vision_logs_maps_limit_and_level(self, coordinator):
        """vision_logs limit/level map to logs() params."""
        result = await coordinator.legacy_vision_logs(limit=10, level="ERROR")
        assert result["ok"] is False
        assert "error" in result

    # ── Metadata is always injected, even on error path ──────────────

    async def test_alias_metadata_survives_error_path(self, coordinator):
        """Metadata is present even when the public tool returns an error."""
        result = await coordinator.legacy_vision_state()
        assert "metadata" in result
        assert result["metadata"]["legacy_tool"] == "vision_state"
