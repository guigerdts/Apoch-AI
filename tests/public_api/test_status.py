"""Tests for apoch_status — ApochCoordinator.status() orchestration.

Spec: mcp-public-api §Tool 1: apoch_status, §Niveles de Confianza
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers 10 scenarios:
  1. Happy path — all modules respond
  2. Problems detected — Guardian reports ERROR severity
  3. Vision timeout — Vision returns None
  4. Guardian timeout — Guardian returns None
  5. Chronicle timeout — Chronicle returns None
  6. All modules timeout — ERR_TIMEOUT
  7. Oracle available — suggested_action from Oracle
  8. Oracle unavailable — default suggested_action
  9. Chronic no events — empty events list
  10. Empty ServiceRegistry — ERR_TIMEOUT
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

import asyncio

import pytest

from apoch.public_api.coordinator import (
    STATUS_RECENT_EVENTS_LIMIT,
    ApochCoordinator,
)
from apoch.public_api.registry import ServiceRegistry

# ── Mock services ─────────────────────────────────────────────────────────────


class _FakeVision:
    """Fake Vision module that returns a fixed module_state."""

    def __init__(self, state: dict | None = None) -> None:
        self._state = state or {"state": "running", "modules": 3}

    async def module_state(self) -> dict:
        """Return the configured state."""
        return self._state


class _SlowVision:
    """Vision module that sleeps beyond the configured timeout."""

    async def module_state(self) -> dict:
        await asyncio.sleep(10)
        return {"state": "running"}


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


class _FakeChronicle:
    """Fake Chronicle module that returns fixed events."""

    def __init__(self, events: list | None = None) -> None:
        # Explicit None check — empty list [] is a valid "no events" value.
        self._events = [{"event": "test"}] if events is None else events

    async def query(self, limit: int = STATUS_RECENT_EVENTS_LIMIT) -> list:
        return self._events[:limit]


class _SlowChronicle:
    """Chronicle module that sleeps beyond the configured timeout."""

    async def query(self, limit: int = STATUS_RECENT_EVENTS_LIMIT) -> list:
        await asyncio.sleep(10)
        return [{"event": "too_late"}]


class _FakeOracle:
    """Fake Oracle module that returns a fixed status."""

    def __init__(self, suggested_action: str = "Ninguna acción requerida") -> None:
        self._suggested_action = suggested_action

    async def status(self) -> dict:
        return {"suggested_action": self._suggested_action}


class _SlowOracle:
    """Oracle module that sleeps beyond the configured timeout."""

    async def status(self) -> dict:
        await asyncio.sleep(10)
        return {"suggested_action": "too_late"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def happy_registry() -> ServiceRegistry:
    """Registry with all 4 services returning happy-path data."""
    registry = ServiceRegistry()
    registry.vision = _FakeVision()
    registry.guardian = _FakeGuardian()
    registry.chronicle = _FakeChronicle()
    registry.oracle = _FakeOracle()
    return registry


@pytest.fixture
def mandatory_registry() -> ServiceRegistry:
    """Registry with 3 mandatory services (no Oracle)."""
    registry = ServiceRegistry()
    registry.vision = _FakeVision()
    registry.guardian = _FakeGuardian()
    registry.chronicle = _FakeChronicle()
    return registry


@pytest.fixture
def problem_registry() -> ServiceRegistry:
    """Registry where Guardian reports an ERROR severity."""
    registry = ServiceRegistry()
    registry.vision = _FakeVision()
    registry.guardian = _FakeGuardian(
        diagnostics=[{"severity": "ERROR", "module": "vision", "message": "Not responding"}],
    )
    registry.chronicle = _FakeChronicle()
    registry.oracle = _FakeOracle()
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestStatusHappyPath:
    """Happy path — all modules respond successfully."""

    async def test_all_modules_respond(self, happy_registry: ServiceRegistry) -> None:
        """All 4 modules respond → 🟢 summary, 4 evidence sources."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.status()

        assert result["summary"] == "🟢 Todos los sistemas operativos"
        assert result["confidence"] == 1.0  # 4/4 — ALL available
        assert len(result["evidence"]) == 4
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "suggested_action" in result
        assert "explanation" in result

    async def test_confidence_is_very_high(self, happy_registry: ServiceRegistry) -> None:
        """All modules available → confidence label is VERY_HIGH (≥0.90)."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.status()
        assert result["confidence"] == 1.0

    async def test_explanation_includes_all_sections(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Explanation mentions components, no errors, and recent activity."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.status()
        expl = result["explanation"]
        # vision_data is a dict with 2 keys → len=2
        assert "2 componentes activos" in expl
        assert "sin errores" in expl
        assert "actividad reciente disponible" in expl

    async def test_suggested_action_default(self, happy_registry: ServiceRegistry) -> None:
        """With Oracle responding, suggested_action comes from Oracle."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.status()
        assert result["suggested_action"] == "Ninguna acción requerida"

    async def test_api_version_present(self, happy_registry: ServiceRegistry) -> None:
        """Response includes api_version field."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.status()
        assert result["api_version"] == "1.0"


class TestStatusProblems:
    """Guardian reports problems — summary shows 🔴."""

    async def test_problems_detected(self, problem_registry: ServiceRegistry) -> None:
        """Guardian reports ERROR → 🔴 summary, problems in explanation."""
        coordinator = ApochCoordinator(problem_registry)
        result = await coordinator.status()

        assert result["summary"] == "🔴 Sistema operativo con problemas detectados"
        assert "problemas detectados" in result["explanation"]

    async def test_suggested_action_when_oracle_and_problems(
        self, problem_registry: ServiceRegistry,
    ) -> None:
        """With Oracle: suggested_action from Oracle even when problems exist."""
        coordinator = ApochCoordinator(problem_registry)
        result = await coordinator.status()
        # Oracle says "Ninguna acción requerida" — problems exist but Oracle's
        # recommendation takes precedence.
        assert result["suggested_action"] == "Ninguna acción requerida"

    async def test_suggested_action_when_no_oracle_and_problems(self) -> None:
        """Without Oracle but with problems → 'Revise los problemas detectados'."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "CRITICAL", "module": "pulse", "message": "Down"}],
        )
        registry.chronicle = _FakeChronicle()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        assert result["summary"] == "🔴 Sistema operativo con problemas detectados"
        assert result["suggested_action"] == "Revise los problemas detectados"

    async def test_problems_confidence(self, problem_registry: ServiceRegistry) -> None:
        """Problems don't reduce confidence — all 4 modules responded."""
        coordinator = ApochCoordinator(problem_registry)
        result = await coordinator.status()
        assert result["confidence"] == 1.0


class TestStatusPartialDegradation:
    """One mandatory module times out → 🟡 degraded."""

    async def test_vision_timeout(self, mandatory_registry: ServiceRegistry) -> None:
        """Vision times out → 🟡, MEDIUM confidence (2/3 mandatory)."""
        registry = mandatory_registry
        registry.vision = _SlowVision()
        coordinator = ApochCoordinator(registry, timeouts={"vision": 0.05})

        result = await coordinator.status()

        assert result["summary"] == "🟡 Sistema funcionando con limitaciones"
        assert result["confidence"] == pytest.approx(0.67, abs=0.01)
        assert len(result["evidence"]) == 2  # only guardian + chronicle

    async def test_guardian_timeout(self, mandatory_registry: ServiceRegistry) -> None:
        """Guardian times out → 🟡, MEDIUM confidence (2/3 mandatory)."""
        registry = mandatory_registry
        registry.guardian = _SlowGuardian()
        coordinator = ApochCoordinator(registry, timeouts={"guardian": 0.05})

        result = await coordinator.status()

        assert result["summary"] == "🟡 Sistema funcionando con limitaciones"
        assert result["confidence"] == pytest.approx(0.67, abs=0.01)
        assert len(result["evidence"]) == 2

    async def test_chronicle_timeout(self, mandatory_registry: ServiceRegistry) -> None:
        """Chronicle times out → 🟡, MEDIUM confidence (2/3 mandatory)."""
        registry = mandatory_registry
        registry.chronicle = _SlowChronicle()
        coordinator = ApochCoordinator(registry, timeouts={"chronicle": 0.05})

        result = await coordinator.status()

        assert result["summary"] == "🟡 Sistema funcionando con limitaciones"
        assert result["confidence"] == pytest.approx(0.67, abs=0.01)
        assert len(result["evidence"]) == 2

    async def test_degraded_explanation_no_chronicle_data(
        self, mandatory_registry: ServiceRegistry,
    ) -> None:
        """Chronicle timeout → explanation mentions missing activity data."""
        registry = mandatory_registry
        registry.chronicle = _SlowChronicle()
        coordinator = ApochCoordinator(registry, timeouts={"chronicle": 0.05})

        result = await coordinator.status()
        assert "sin datos de actividad reciente" in result["explanation"]

    async def test_degraded_explanation_vision_timeout(
        self,
    ) -> None:
        """Vision timeout → explanation skips active components."""
        registry = ServiceRegistry()
        registry.vision = _SlowVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle()
        coordinator = ApochCoordinator(registry, timeouts={"vision": 0.05})

        result = await coordinator.status()
        expl = result["explanation"]
        assert "sin errores" in expl
        assert "actividad reciente disponible" in expl
        # No mention of components since vision timed out
        assert "componentes activos" not in expl


class TestStatusAllTimeout:
    """All modules time out → ERR_TIMEOUT."""

    async def test_all_slow(self) -> None:
        """All modules timeout → ERR_TIMEOUT error response."""
        registry = ServiceRegistry()
        registry.vision = _SlowVision()
        registry.guardian = _SlowGuardian()
        registry.chronicle = _SlowChronicle()
        coordinator = ApochCoordinator(
            registry,
            timeouts={"vision": 0.05, "guardian": 0.05, "chronicle": 0.05},
        )

        result = await coordinator.status()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"
        assert "No modules responded" in result["error"]["message"]

    async def test_empty_service_registry(self, empty_registry: ServiceRegistry) -> None:
        """No services loaded → no queries → ERR_TIMEOUT."""
        coordinator = ApochCoordinator(empty_registry)
        result = await coordinator.status()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"
        assert "No modules responded" in result["error"]["message"]


class TestStatusOracle:
    """Oracle behaviour — availability and content."""

    async def test_oracle_suggested_action_from_oracle(self) -> None:
        """Oracle responds with custom action → used as suggested_action."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle()
        registry.oracle = _FakeOracle(suggested_action="Revisar módulo Vision")

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        assert result["suggested_action"] == "Revisar módulo Vision"

    async def test_oracle_returns_none_suggested_action(self) -> None:
        """Oracle returns None suggested_action → falls back to default."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle()
        registry.oracle = _FakeOracle(suggested_action="")

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        # Empty string is falsy → falls back to "Ninguna acción requerida"
        assert result["suggested_action"] == "Ninguna acción requerida"

    async def test_oracle_not_available(self) -> None:
        """Oracle service is None → suggested_action falls back to default."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle()
        # oracle is None by default

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        assert result["suggested_action"] == "Ninguna acción requerida"


class TestStatusChronicleNoEvents:
    """Chronicle returns empty events — edge case handling."""

    async def test_empty_events(self) -> None:
        """Chronicle returns empty list → explanation mentions no registered activity."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle(events=[])
        registry.oracle = _FakeOracle()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        # All mandatory respond → 🟢
        assert result["summary"] == "🟢 Todos los sistemas operativos"
        # Explanation mentions no activity data because events list is empty
        assert "sin actividad registrada" in result["explanation"]
        # Confidence still 1.0 (chronicle responded, just no events)
        assert result["confidence"] == 1.0
        # 4 evidence sources (all modules responded)
        assert len(result["evidence"]) == 4


class TestStatusServiceNotAvailable:
    """Service is loaded but its required method is missing."""

    async def test_vision_without_module_state(self) -> None:
        """Vision has no module_state method → not queried (skipped entirely)."""
        registry = ServiceRegistry()

        class _NoMethodVision:  # noqa: F811
            pass

        registry.vision = _NoMethodVision()
        registry.guardian = _FakeGuardian()
        registry.chronicle = _FakeChronicle()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.status()

        # Vision has no module_state → not added to queries.
        # Only 2 modules queried, both respond → 1.0 confidence.
        # But mandatory "vision" is absent from results → all_mandatory=False → 🟡.
        assert result["summary"] == "🟡 Sistema funcionando con limitaciones"
        assert result["confidence"] == 1.0
        assert len(result["evidence"]) == 2


class TestStatusCoordinatorLifecycle:
    """Coordinator construction and tool def registration."""

    def test_get_tool_defs_returns_apoch_status(self) -> None:
        """get_tool_defs returns exactly one ToolDef for apoch_status."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 1
        assert defs[0].name == "apoch_status"
        assert defs[0].handler_name == "status"
        assert defs[0].description
        assert defs[0].input_schema == {"type": "object", "properties": {}}

    def test_get_tool_defs_is_classmethod(self) -> None:
        """get_tool_defs works on the class, not just instances."""
        # Call via class directly
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 1

        # Call via instance also works
        coordinator = ApochCoordinator(ServiceRegistry())
        defs_via_instance = coordinator.get_tool_defs()
        assert len(defs_via_instance) == 1
        assert defs_via_instance[0].name == "apoch_status"


class TestStatusOtherToolsStillStubs:
    """Non-status tools still return ERR_NOT_IMPLEMENTED."""

    @pytest.fixture
    def coordinator(self) -> ApochCoordinator:
        return ApochCoordinator(ServiceRegistry())

    async def test_history_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.history()
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_NOT_IMPLEMENTED"

    async def test_health_stub(self, coordinator: ApochCoordinator) -> None:
        result = await coordinator.health()
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
