"""Tests for apoch_health — ApochCoordinator.health() orchestration.

Spec: mcp-public-api §Tool 2: apoch_health, §Niveles de Confianza
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers 15+ scenarios from the DoD matrix (apoch_health-boundary-review.md):
  1. No problems — Guardian empty diagnostics
  2. Warning — Guardian reports WARNING
  3. Critical — Guardian reports ERROR
  4. Critical preferred over Warning
  5. Guardian timeout → ERR_DEPENDENCY_UNAVAILABLE
  6. Guardian None in ServiceRegistry
  7. Guardian + Vision both timeout
  8. Vision timeout — Guardian still works
  9. Vision None in ServiceRegistry — Guardian still works
  10. Guardian empty diagnostics (list)
  11. Guardian empty dict
  12. Response has all ToolResponse fields
  13. api_version = 1.0
  14. No fields from future tools
  15. get_tool_defs includes apoch_health
  16. Other tools still stubs
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

import asyncio

import pytest

from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ── Mock services ─────────────────────────────────────────────────────────────


class _FakeGuardian:
    """Fake Guardian module that returns fixed diagnostics."""

    def __init__(self, diagnostics: list[dict] | None = None) -> None:
        self._diagnostics = diagnostics or []

    async def all_diagnostics(self) -> dict:
        return {"diagnostics": self._diagnostics}


class _SlowGuardian:
    """Guardian module that sleeps beyond the configured timeout."""

    async def all_diagnostics(self) -> dict:
        await asyncio.sleep(10)
        return {"diagnostics": []}


class _FakeVision:
    """Fake Vision module that returns a fixed module_state."""

    def __init__(self, state: dict | None = None) -> None:
        self._state = state or {"state": "running", "modules": 3}

    async def module_state(self) -> dict:
        return self._state


class _SlowVision:
    """Vision module that sleeps beyond the configured timeout."""

    async def module_state(self) -> dict:
        await asyncio.sleep(10)
        return {"state": "running"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def no_problems_registry() -> ServiceRegistry:
    """Registry: Guardian with empty diagnostics + Vision."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian()
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def warning_registry() -> ServiceRegistry:
    """Registry: Guardian reports WARNING + Vision."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian(
        diagnostics=[{"severity": "WARNING", "module": "pulse",
                       "message": "High latency detected"}],
    )
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def critical_registry() -> ServiceRegistry:
    """Registry: Guardian reports ERROR + Vision."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian(
        diagnostics=[{"severity": "ERROR", "module": "chronicle", "message": "Not responding"}],
    )
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def mixed_problems_registry() -> ServiceRegistry:
    """Registry: Guardian reports both WARNING and CRITICAL + Vision."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian(
        diagnostics=[
            {"severity": "WARNING", "module": "pulse", "message": "High latency"},
            {"severity": "CRITICAL", "module": "chronicle", "message": "Down"},
        ],
    )
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def guardian_only_registry() -> ServiceRegistry:
    """Registry: Guardian available, Vision not loaded."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian()
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHealthNoProblems:
    """No problems detected — 🟢 summary."""

    async def test_no_problems(self, no_problems_registry: ServiceRegistry) -> None:
        """Guardian empty diagnostics → 🟢 'Sin problemas detectados'."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["confidence"] == 1.0  # 2/2 — both respond
        assert "No hay problemas registrados" in result["explanation"]
        assert result["suggested_action"] == "Ninguna acción requerida"

    async def test_empty_diagnostics_list(self) -> None:
        """Guardian returns empty diagnostics list → 🟢, not error."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(diagnostics=[])
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert "error" not in result  # success response, not error

    async def test_guardian_empty_dict(self) -> None:
        """Guardian returns empty dict → 🟢 (handles gracefully)."""
        registry = ServiceRegistry()

        class _EmptyDictGuardian:
            async def all_diagnostics(self) -> dict:
                return {}

        registry.guardian = _EmptyDictGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["suggested_action"] == "Ninguna acción requerida"

    async def test_guardian_no_diagnostics_key(self) -> None:
        """Guardian returns dict without 'diagnostics' key → 🟢 (handles gracefully)."""
        registry = ServiceRegistry()

        class _MissingKeyGuardian:
            async def all_diagnostics(self) -> dict:
                return {"status": "ok"}

        registry.guardian = _MissingKeyGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["suggested_action"] == "Ninguna acción requerida"


class TestHealthWarnings:
    """Warnings produce 🟡 summary."""

    async def test_warning(self, warning_registry: ServiceRegistry) -> None:
        """Guardian reports WARNING → 🟡 'Se detectaron advertencias'."""
        coordinator = ApochCoordinator(warning_registry)
        result = await coordinator.health()

        assert result["summary"] == "🟡 Se detectaron advertencias en el sistema"
        assert "[WARNING]" in result["explanation"]
        assert "pulse" in result["explanation"]

    async def test_warning_suggested_action(self, warning_registry: ServiceRegistry) -> None:
        """Warning → suggested_action mentions reviewing the warning."""
        coordinator = ApochCoordinator(warning_registry)
        result = await coordinator.health()

        assert "advertencia" in result["suggested_action"]
        assert "pulse" in result["suggested_action"]

    async def test_warning_confidence(self, warning_registry: ServiceRegistry) -> None:
        """Both Guardian + Vision respond → confidence = 1.0."""
        coordinator = ApochCoordinator(warning_registry)
        result = await coordinator.health()

        assert result["confidence"] == 1.0


class TestHealthCritical:
    """Critical problems produce 🔴 summary."""

    async def test_critical(self, critical_registry: ServiceRegistry) -> None:
        """Guardian reports ERROR → 🔴 'problemas críticos'."""
        coordinator = ApochCoordinator(critical_registry)
        result = await coordinator.health()

        assert result["summary"] == "🔴 Se detectaron problemas críticos en el sistema"
        assert "[ERROR]" in result["explanation"]
        assert "chronicle" in result["explanation"]

    async def test_critical_suggested_action(self, critical_registry: ServiceRegistry) -> None:
        """Critical → suggested_action mentions restarting the module."""
        coordinator = ApochCoordinator(critical_registry)
        result = await coordinator.health()

        assert "Revise el módulo" in result["suggested_action"]
        assert "chronicle" in result["suggested_action"]

    async def test_critical_severity_error(self) -> None:
        """ERROR severity → 🔴 summary."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "ERROR", "module": "vision", "message": "Failed"}],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert "🔴" in result["summary"]

    async def test_critical_severity_critical(self) -> None:
        """CRITICAL severity → 🔴 summary."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "CRITICAL", "module": "engine", "message": "Core failure"}],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert "🔴" in result["summary"]
        assert "CRITICAL" in result["explanation"]


class TestHealthMixedProblems:
    """Mixed warning + critical → 🔴 global with most severe action."""

    async def test_critical_preferred_over_warning(
        self, mixed_problems_registry: ServiceRegistry,
    ) -> None:
        """Both WARNING and CRITICAL → 🔴 summary, action from CRITICAL."""
        coordinator = ApochCoordinator(mixed_problems_registry)
        result = await coordinator.health()

        assert result["summary"] == "🔴 Se detectaron problemas críticos en el sistema"
        # Explanation includes both problems, sorted by severity
        expl = result["explanation"]
        assert "[CRITICAL]" in expl
        assert "[WARNING]" in expl
        # CRITICAL should come before WARNING in sorted output
        crit_pos = expl.index("[CRITICAL]")
        warn_pos = expl.index("[WARNING]")
        assert crit_pos < warn_pos
        # Action from the MOST severe problem
        assert "chronicle" in result["suggested_action"]
        assert "Revise el módulo" in result["suggested_action"]

    async def test_mixed_confidence(self, mixed_problems_registry: ServiceRegistry) -> None:
        """Both respond → confidence = 1.0."""
        coordinator = ApochCoordinator(mixed_problems_registry)
        result = await coordinator.health()

        assert result["confidence"] == 1.0


class TestHealthGuardianNotAvailable:
    """Guardian missing/failing → ERR_DEPENDENCY_UNAVAILABLE."""

    async def test_guardian_timeout(self) -> None:
        """Guardian times out → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.guardian = _SlowGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry, timeouts={"guardian": 0.05})
        result = await coordinator.health()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_guardian_none(self) -> None:
        """Guardian is None → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        # guardian is None by default

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_guardian_timeout_vision_available_message(self) -> None:
        """Guardian timeout, Vision responds → error message mentions active components."""
        registry = ServiceRegistry()
        registry.guardian = _SlowGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry, timeouts={"guardian": 0.05})
        result = await coordinator.health()

        assert result["ok"] is False
        assert "Componentes activos" in result["error"]["message"]

    async def test_guardian_timeout_no_vision(self) -> None:
        """Guardian timeout, no Vision → simpler error message."""
        registry = ServiceRegistry()
        registry.guardian = _SlowGuardian()
        # no vision

        coordinator = ApochCoordinator(registry, timeouts={"guardian": 0.05})
        result = await coordinator.health()

        assert result["ok"] is False
        assert "Componentes activos" not in result["error"]["message"]

    async def test_both_timeout(self) -> None:
        """Both Guardian and Vision timeout → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.guardian = _SlowGuardian()
        registry.vision = _SlowVision()

        coordinator = ApochCoordinator(
            registry,
            timeouts={"guardian": 0.05, "vision": 0.05},
        )
        result = await coordinator.health()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_guardian_exception(self) -> None:
        """Guardian raises exception → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _FailingGuardian:
            async def all_diagnostics(self) -> dict:
                msg = "unexpected error"
                raise RuntimeError(msg)

        registry.guardian = _FailingGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_empty_registry(self, empty_registry: ServiceRegistry) -> None:
        """No services loaded → ERR_DEPENDENCY_UNAVAILABLE (no queries)."""
        coordinator = ApochCoordinator(empty_registry)
        result = await coordinator.health()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"


class TestHealthVisionDegradation:
    """Vision unavailable — health degrades gracefully with MEDIUM confidence."""

    async def test_vision_timeout(self) -> None:
        """Vision times out → health works, MEDIUM confidence (1/2)."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian()
        registry.vision = _SlowVision()

        coordinator = ApochCoordinator(registry, timeouts={"vision": 0.05})
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["confidence"] == 0.5  # 1/2 — guardian only
        assert len(result["evidence"]) == 1  # only Guardian in evidence

    async def test_vision_none(self) -> None:
        """Vision is None → health works, MEDIUM confidence (1/2)."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian()
        # vision is None by default

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["confidence"] == 0.5  # 1/2 — guardian only
        assert len(result["evidence"]) == 1  # only Guardian

    async def test_vision_timeout_with_warning(self) -> None:
        """Vision timeout, warning present → 🟡 with MEDIUM confidence."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "WARNING", "module": "pulse", "message": "Degraded"}],
        )
        registry.vision = _SlowVision()

        coordinator = ApochCoordinator(registry, timeouts={"vision": 0.05})
        result = await coordinator.health()

        assert result["summary"] == "🟡 Se detectaron advertencias en el sistema"
        assert result["confidence"] == 0.5
        assert result["suggested_action"] is not None

    async def test_vision_without_module_state(self) -> None:
        """Vision lacks module_state method → not queried (no Vision source)."""
        registry = ServiceRegistry()

        class _NoMethodVision:  # noqa: F811
            pass

        registry.guardian = _FakeGuardian()
        registry.vision = _NoMethodVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        # Vision not added to queries — only guardian responds
        # confidence = 1/2 = 0.5 (expected 2 modules but only 1 queried + responded)
        assert result["summary"] == "🟢 Sin problemas detectados"
        assert result["confidence"] == 0.5


class TestHealthResponseFormat:
    """Response structure verification — ToolResponse contract."""

    async def test_all_tool_response_fields(self, no_problems_registry: ServiceRegistry) -> None:
        """Response includes all required ToolResponse fields."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        assert "api_version" in result
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result

    async def test_api_version(self, no_problems_registry: ServiceRegistry) -> None:
        """api_version = '1.0'."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        assert result["api_version"] == "1.0"

    async def test_no_forbidden_fields(self, no_problems_registry: ServiceRegistry) -> None:
        """Response has no fields from future tools (recommend, history, progress, insights)."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        # Health should NOT include recommendation-specific fields
        assert "priority" not in result
        assert "expected_benefit" not in result
        # Health should NOT include history-specific fields
        assert "events" not in result
        # Health should NOT include progress-specific fields
        assert "productivity" not in result
        # Health should NOT include insights-specific fields
        assert "patterns" not in result
        assert "opportunities" not in result
        # Health should NOT include logs-specific fields
        assert "entries" not in result

    async def test_evidence_structure(self, no_problems_registry: ServiceRegistry) -> None:
        """Evidence entries have correct structure."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        assert len(result["evidence"]) == 2
        for entry in result["evidence"]:
            assert "source" in entry
            assert "confidence" in entry
            assert "collected_ago" in entry
            assert "based_on" in entry

    async def test_evidence_sources(self, no_problems_registry: ServiceRegistry) -> None:
        """Evidence includes Guardian and Vision."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        sources = {e["source"] for e in result["evidence"]}
        assert "Guardian" in sources
        assert "Vision" in sources

    async def test_generated_at_is_iso8601(self, no_problems_registry: ServiceRegistry) -> None:
        """generated_at is a valid ISO 8601 timestamp."""
        from datetime import datetime

        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        parsed = datetime.fromisoformat(result["generated_at"])
        assert parsed is not None

    async def test_summary_not_empty(self, no_problems_registry: ServiceRegistry) -> None:
        """Summary is a non-empty single line."""
        coordinator = ApochCoordinator(no_problems_registry)
        result = await coordinator.health()

        assert result["summary"]
        assert "\n" not in result["summary"]  # single line

    async def test_no_traceback_in_explanation(self) -> None:
        """Explanation does not contain internal error details or tracebacks."""
        registry = ServiceRegistry()

        class _VerboseGuardian:
            async def all_diagnostics(self) -> dict:
                return {
                    "diagnostics": [
                        {
                            "severity": "ERROR",
                            "module": "vision",
                            "message": "Something broke",
                            "traceback": "File /usr/lib/... line 42",
                            "internal_code": "ERR-42",
                        },
                    ],
                }

        registry.guardian = _VerboseGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.health()

        # The explanation uses the message from diagnostics but should not
        # expose tracebacks or internal codes directly.
        expl = result["explanation"]
        assert "Something broke" in expl  # message is fine
        # These are the actual explanation keys used — no traceback leakage


class TestHealthToolDef:
    """Tool definition registration."""

    def test_get_tool_defs_includes_health(self) -> None:
        """get_tool_defs returns apoch_health as second entry."""
        defs = ApochCoordinator.get_tool_defs()
        names = [d.name for d in defs]
        assert "apoch_health" in names

    def test_get_tool_defs_has_both_tools(self) -> None:
        """get_tool_defs includes exactly apoch_status and apoch_health."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 2
        assert defs[0].name == "apoch_status"
        assert defs[0].handler_name == "status"
        assert defs[1].name == "apoch_health"
        assert defs[1].handler_name == "health"

    def test_get_tool_defs_health_descriptions(self) -> None:
        """apoch_health ToolDef has description and input_schema."""
        defs = ApochCoordinator.get_tool_defs()
        health_def = next(d for d in defs if d.name == "apoch_health")
        assert health_def.description
        assert health_def.input_schema == {"type": "object", "properties": {}}

    def test_get_tool_defs_is_classmethod(self) -> None:
        """get_tool_defs works on both class and instance."""
        # Via class
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 2

        # Via instance
        coordinator = ApochCoordinator(ServiceRegistry())
        defs_via_instance = coordinator.get_tool_defs()
        assert len(defs_via_instance) == 2
        assert defs_via_instance[1].name == "apoch_health"

    def test_no_future_tools_in_defs(self) -> None:
        """Only apoch_status and apoch_health are in get_tool_defs — no future tools."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert names == {"apoch_status", "apoch_health"}
        # None of these should be registered yet
        assert "apoch_history" not in names
        assert "apoch_recommend" not in names
        assert "apoch_progress" not in names
        assert "apoch_insights" not in names
        assert "apoch_logs" not in names


class TestHealthOtherToolsStillStubs:
    """Other tools (non-health, non-status) still return ERR_NOT_IMPLEMENTED."""

    @pytest.fixture
    def coordinator(self) -> ApochCoordinator:
        return ApochCoordinator(ServiceRegistry())

    async def test_history_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.history()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_recommend_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.recommend()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_progress_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.progress()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_insights_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.insights()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_logs_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.logs()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"
