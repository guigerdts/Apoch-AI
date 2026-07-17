"""Tests for apoch_recommend — ApochCoordinator.recommend() orchestration.

Spec: mcp-public-api §Tool 4: apoch_recommend, §RecommendResponse
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers:
  1. Oracle happy path — recommendations available
  2. Oracle priority mapping (critical/high → HIGH, medium → MEDIUM, low → LOW)
  3. Oracle empty list → fallback Guardian+Vision
  4. Oracle unavailable (None) → fallback
  5. Oracle timeout → fallback
  6. Guardian ERROR → priority HIGH summary
  7. Guardian WARNING → priority MEDIUM summary
  8. Guardian mixed (ERROR + WARNING) → ERROR takes precedence
  9. No problems → "No hay recomendaciones", priority LOW, confidence HIGH
  10. Guardian+Vision healthy → no recommendations
  11. All three timeout → ERR_TIMEOUT
  12. All three None → ERR_TIMEOUT
  13. suggested_action is always None
  14. Response has all RecommendResponse fields
  15. Evidence uses functional labels (P6)
  16. get_tool_defs includes apoch_recommend
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

import asyncio

import pytest

from apoch.modules.guardian.diagnostics import ModuleDiagnostics
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ── Mock services ─────────────────────────────────────────────────────────────


class _FakeRecommendation:
    """Simplified Recommendation-like object for test mocks.

    Matches the fields that ApochCoordinator.recommend() consumes:
    ``title``, ``justification``, ``priority``, ``confidence``.
    """

    def __init__(
        self,
        title: str = "Reiniciar módulo Guardian",
        justification: str = "Alta tasa de errores detectada en Guardian",
        priority: str = "high",
        confidence: float = 0.85,
    ) -> None:
        self.title = title
        self.justification = justification
        self.priority = priority
        self.confidence = confidence


class _FakeOracle:
    """Fake Oracle module returning a fixed list of recommendations."""

    def __init__(self, recommendations: list | None = None) -> None:
        self._recommendations = recommendations or []

    @property
    def services(self) -> dict:
        return {"oracle.recommendations": lambda: self._recommendations}


class _SlowOracle:
    """Oracle module that sleeps beyond the configured timeout."""

    @property
    def services(self) -> dict:
        async def _slow() -> list:
            await asyncio.sleep(10)
            return []

        return {"oracle.recommendations": _slow}


class _FakeGuardian:
    """Fake Guardian module that returns fixed diagnostics.

    Accepts test-friendly ``list[dict]`` and converts internally to
    real ``ModuleDiagnostics`` format.
    """

    def __init__(self, diagnostics: list[dict] | None = None) -> None:
        raw = diagnostics or []
        self._diagnostics: dict[str, ModuleDiagnostics] = {}
        for d in raw:
            mod = d.get("module", "unknown")
            sev = d.get("severity", "WARNING")
            msg = d.get("message", "")
            state = "FAILED" if sev in ("ERROR", "CRITICAL") else "RUNNING"
            self._diagnostics[mod] = ModuleDiagnostics(
                module_name=mod,
                current_state=state,
                last_error=msg or None,
                last_error_traceback=None,
                fail_count=1 if state == "FAILED" else 0,
                last_failure_time=(
                    "2026-07-16T12:00:00" if state == "FAILED" else None
                ),
            )

    async def all_diagnostics(self) -> dict[str, ModuleDiagnostics]:
        return dict(self._diagnostics)


class _SlowGuardian:
    """Guardian module that sleeps beyond the configured timeout."""

    async def all_diagnostics(self) -> dict[str, ModuleDiagnostics]:
        await asyncio.sleep(10)
        return {}


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
def oracle_happy_registry() -> ServiceRegistry:
    """Registry: Oracle returns 3 recs + healthy Guardian + Vision."""
    registry = ServiceRegistry()
    registry.oracle = _FakeOracle(recommendations=[
        _FakeRecommendation(
            title="Reiniciar módulo Guardian",
            justification="Alta tasa de errores en Guardian",
            priority="high",
            confidence=0.85,
        ),
        _FakeRecommendation(
            title="Aumentar recursos de Vision",
            justification="Vision cerca del límite de memoria",
            priority="medium",
            confidence=0.65,
        ),
        _FakeRecommendation(
            title="Actualizar configuración de Chronicle",
            justification="Chronicle usa configuración por defecto",
            priority="low",
            confidence=0.40,
        ),
    ])
    registry.guardian = _FakeGuardian()
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def oracle_empty_registry() -> ServiceRegistry:
    """Registry: Oracle returns empty list + healthy Guardian + Vision."""
    registry = ServiceRegistry()
    registry.oracle = _FakeOracle(recommendations=[])
    registry.guardian = _FakeGuardian()
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def guardian_error_registry() -> ServiceRegistry:
    """Registry: Guardian has ERROR, no Oracle, Vision healthy."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian(
        diagnostics=[{"severity": "ERROR", "module": "chronicle", "message": "Not responding"}],
    )
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def guardian_warning_registry() -> ServiceRegistry:
    """Registry: Guardian has WARNING, no Oracle, Vision healthy."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian(
        diagnostics=[{"severity": "WARNING", "module": "pulse", "message": "High latency"}],
    )
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def healthy_registry() -> ServiceRegistry:
    """Registry: no Oracle, healthy Guardian, healthy Vision."""
    registry = ServiceRegistry()
    registry.guardian = _FakeGuardian()
    registry.vision = _FakeVision()
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


# ── Tests: Oracle happy path ──────────────────────────────────────────────────


class TestRecommendOracleAvailable:
    """Oracle returns recommendations — happy path."""

    async def test_uses_first_recommendation(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """Oracle returns 3 recs → summary = first rec title."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["summary"] == "Reiniciar módulo Guardian"
        assert "Alta tasa de errores" in result["explanation"]

    async def test_priority_mapped_to_high(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """Oracle 'high' priority → 'HIGH' in response."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["priority"] == "HIGH"

    async def test_confidence_from_oracle(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """Confidence comes from Oracle recommendation."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["confidence"] == 0.85

    async def test_suggested_action_is_none(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """suggested_action is always None per spec."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["suggested_action"] is None

    async def test_priority_critical_maps_to_high(self) -> None:
        """Oracle 'critical' priority → 'HIGH'."""
        registry = ServiceRegistry()
        registry.oracle = _FakeOracle(recommendations=[
            _FakeRecommendation(priority="critical"),
        ])
        registry.guardian = _FakeGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert result["priority"] == "HIGH"

    async def test_priority_medium_stays_medium(self) -> None:
        """Oracle 'medium' priority → 'MEDIUM'."""
        registry = ServiceRegistry()
        registry.oracle = _FakeOracle(recommendations=[
            _FakeRecommendation(priority="medium"),
        ])
        registry.guardian = _FakeGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert result["priority"] == "MEDIUM"

    async def test_priority_low_stays_low(self) -> None:
        """Oracle 'low' priority → 'LOW'."""
        registry = ServiceRegistry()
        registry.oracle = _FakeOracle(recommendations=[
            _FakeRecommendation(priority="low"),
        ])
        registry.guardian = _FakeGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert result["priority"] == "LOW"


# ── Tests: Oracle empty / unavailable → fallback ──────────────────────────────


class TestRecommendOracleEmptyFallback:
    """Oracle returns no recommendations — falls back to Guardian+Vision."""

    async def test_oracle_empty_uses_guardian_fallback(
        self, oracle_empty_registry: ServiceRegistry,
    ) -> None:
        """Oracle empty list → fallback to Guardian+Vision produces 'No hay'. """
        coordinator = ApochCoordinator(oracle_empty_registry)
        result = await coordinator.recommend()

        assert result["summary"] == "No hay recomendaciones en este momento."
        assert result["priority"] == "LOW"
        assert result["confidence"] == 0.85

    async def test_oracle_empty_with_guardian_error(self) -> None:
        """Oracle empty + Guardian ERROR → fallback produces recommendation."""
        registry = ServiceRegistry()
        registry.oracle = _FakeOracle(recommendations=[])
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "ERROR", "module": "chronicle", "message": "Down"}],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert "chronicle" in result["summary"]
        assert result["priority"] == "HIGH"
        assert result["suggested_action"] is None


class TestRecommendOracleUnavailable:
    """Oracle not available — falls back to Guardian+Vision."""

    async def test_no_oracle_guardian_error(
        self, guardian_error_registry: ServiceRegistry,
    ) -> None:
        """No Oracle + Guardian ERROR → priority HIGH, summary mentions module."""
        coordinator = ApochCoordinator(guardian_error_registry)
        result = await coordinator.recommend()

        assert "chronicle" in result["summary"]
        assert result["priority"] == "HIGH"
        assert result["suggested_action"] is None

    async def test_no_oracle_guardian_warning(
        self, guardian_warning_registry: ServiceRegistry,
    ) -> None:
        """No Oracle + Guardian WARNING → priority MEDIUM."""
        coordinator = ApochCoordinator(guardian_warning_registry)
        result = await coordinator.recommend()

        assert "pulse" in result["summary"]
        assert result["priority"] == "MEDIUM"
        assert result["suggested_action"] is None

    async def test_no_oracle_healthy(
        self, healthy_registry: ServiceRegistry,
    ) -> None:
        """No Oracle + healthy → 'No hay recomendaciones', priority LOW, confidence HIGH."""
        coordinator = ApochCoordinator(healthy_registry)
        result = await coordinator.recommend()

        assert result["summary"] == "No hay recomendaciones en este momento."
        assert result["priority"] == "LOW"
        assert result["confidence"] == 1.0
        assert result["suggested_action"] is None

    async def test_oracle_timeout_fallback_to_guardian(self) -> None:
        """Oracle times out → fallback to Guardian."""
        registry = ServiceRegistry()
        registry.oracle = _SlowOracle()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "WARNING", "module": "pulse", "message": "Slow"}],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry, timeouts={"oracle": 0.05})
        result = await coordinator.recommend()

        assert "pulse" in result["summary"]
        assert result["priority"] == "MEDIUM"
        assert result["suggested_action"] is None


# ── Tests: Guardian fallback details ──────────────────────────────────────────


class TestRecommendGuardianFallback:
    """Guardian fallback behavior — severity mapping and error handling."""

    async def test_mixed_severity_error_takes_precedence(self) -> None:
        """Both ERROR and WARNING → ERROR wins, priority HIGH."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[
                {"severity": "WARNING", "module": "pulse", "message": "High latency"},
                {"severity": "ERROR", "module": "chronicle", "message": "Not responding"},
            ],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert "chronicle" in result["summary"]
        assert result["priority"] == "HIGH"

    async def test_vision_not_available_guardian_works(self) -> None:
        """Guardian works even without Vision."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "WARNING", "module": "pulse", "message": "Slow"}],
        )

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert result["priority"] == "MEDIUM"
        assert result["summary"] != "No hay recomendaciones en este momento."

    async def test_guardian_not_available_healthy(self) -> None:
        """No Guardian, Vision healthy → 'No hay recomendaciones'."""
        registry = ServiceRegistry()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert result["summary"] == "No hay recomendaciones en este momento."
        assert result["priority"] == "LOW"
        assert result["confidence"] == 1.0

    async def test_explanation_contains_severity_label(self) -> None:
        """Explanation includes [ERROR] or [WARNING] label."""
        registry = ServiceRegistry()
        registry.guardian = _FakeGuardian(
            diagnostics=[{"severity": "ERROR", "module": "chronicle", "message": "Down"}],
        )
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.recommend()

        assert "[ERROR]" in result["explanation"]
        assert "chronicle" in result["explanation"]
        assert "Down" in result["explanation"]


# ── Tests: Timeout / error scenarios ──────────────────────────────────────────


class TestRecommendTimeouts:
    """Module timeouts and unavailability."""

    async def test_all_three_timeout(self) -> None:
        """Oracle, Guardian, Vision all timeout → ERR_TIMEOUT."""
        registry = ServiceRegistry()
        registry.oracle = _SlowOracle()
        registry.guardian = _SlowGuardian()
        registry.vision = _SlowVision()

        coordinator = ApochCoordinator(
            registry,
            timeouts={"oracle": 0.05, "guardian": 0.05, "vision": 0.05},
        )
        result = await coordinator.recommend()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"

    async def test_empty_registry(self, empty_registry: ServiceRegistry) -> None:
        """No services loaded → ERR_TIMEOUT."""
        coordinator = ApochCoordinator(empty_registry)
        result = await coordinator.recommend()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"

    async def test_oracle_times_out_guardian_and_vision_ok(self) -> None:
        """Oracle timeout, Guardian healthy → no recommendations (not timeout)."""
        registry = ServiceRegistry()
        registry.oracle = _SlowOracle()
        registry.guardian = _FakeGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry, timeouts={"oracle": 0.05})
        result = await coordinator.recommend()

        # Should NOT be ERR_TIMEOUT — Guardian+Vision responded
        assert result.get("ok") is not False
        assert result["summary"] == "No hay recomendaciones en este momento."
        assert result["priority"] == "LOW"

    async def test_oracle_exception_handled(self) -> None:
        """Oracle raises exception → treated as unavailable, fallback works."""
        registry = ServiceRegistry()

        class _FailingOracle:
            @property
            def services(self) -> dict:
                def _fail() -> list:
                    msg = "oracle error"
                    raise RuntimeError(msg)
                return {"oracle.recommendations": _fail}

        registry.oracle = _FailingOracle()
        registry.guardian = _FakeGuardian()
        registry.vision = _FakeVision()

        coordinator = ApochCoordinator(registry, timeouts={"oracle": 0.05})
        result = await coordinator.recommend()

        # Fallback should work — Guardian+Vision available
        assert result["summary"] == "No hay recomendaciones en este momento."


# ── Tests: Response contract ──────────────────────────────────────────────────


class TestRecommendResponseFormat:
    """RecommendResponse contract verification."""

    async def test_all_recommend_fields(self, oracle_happy_registry: ServiceRegistry) -> None:
        """Response includes all ToolResponse + RecommendResponse fields."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert "api_version" in result
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "priority" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result

    async def test_api_version(self, oracle_happy_registry: ServiceRegistry) -> None:
        """api_version is '1.0'."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["api_version"] == "1.0"

    async def test_no_forbidden_fields(self, oracle_happy_registry: ServiceRegistry) -> None:
        """No fields from other tools (status, health, history, etc.)."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        # Should NOT have fields from other tools
        assert "diagnostics" not in result
        assert "events" not in result
        assert "productivity" not in result
        assert "patterns" not in result
        assert "opportunities" not in result
        assert "entries" not in result

    async def test_evidence_functional_labels_oracle(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """Evidence uses functional labels (P6), not module names."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        sources = {e["source"] for e in result["evidence"]}
        # Functional labels, not "Oracle", "Guardian", "Vision"
        assert "Sistema de recomendaciones" in sources
        assert "Diagnóstico del sistema" in sources
        assert "Estado de componentes" in sources
        # No internal module names
        assert "Oracle" not in sources
        assert "Guardian" not in sources
        assert "Vision" not in sources

    async def test_evidence_functional_labels_fallback(
        self, guardian_error_registry: ServiceRegistry,
    ) -> None:
        """Fallback evidence uses functional labels."""
        coordinator = ApochCoordinator(guardian_error_registry)
        result = await coordinator.recommend()

        sources = {e["source"] for e in result["evidence"]}
        assert "Diagnóstico del sistema" in sources
        assert "Estado de componentes" in sources

    async def test_generated_at_is_iso8601(
        self, oracle_happy_registry: ServiceRegistry,
    ) -> None:
        """generated_at is a valid ISO 8601 timestamp."""
        from datetime import datetime

        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        parsed = datetime.fromisoformat(result["generated_at"])
        assert parsed is not None

    async def test_summary_not_empty(self, oracle_happy_registry: ServiceRegistry) -> None:
        """Summary is a non-empty single line."""
        coordinator = ApochCoordinator(oracle_happy_registry)
        result = await coordinator.recommend()

        assert result["summary"]
        assert "\n" not in result["summary"]


# ── Tests: Tool definition registration ───────────────────────────────────────


class TestRecommendToolDef:
    """Tool definition registration for apoch_recommend."""

    def test_get_tool_defs_includes_recommend(self) -> None:
        """get_tool_defs includes apoch_recommend."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert "apoch_recommend" in names

    def test_get_tool_defs_has_seven_tools(self) -> None:
        """get_tool_defs has exactly 7 tools now (PR8 — apoch_logs added)."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 7

    def test_get_tool_defs_recommend_handler(self) -> None:
        """apoch_recommend handler is 'recommend'."""
        defs = ApochCoordinator.get_tool_defs()
        recommend_def = next(d for d in defs if d.name == "apoch_recommend")
        assert recommend_def.handler_name == "recommend"
        assert recommend_def.description
        assert recommend_def.input_schema == {"type": "object", "properties": {}}

    def test_get_tool_defs_is_classmethod(self) -> None:
        """get_tool_defs works on both class and instance (7 tools PR8)."""
        defs_via_class = ApochCoordinator.get_tool_defs()
        coordinator = ApochCoordinator(ServiceRegistry())
        defs_via_instance = coordinator.get_tool_defs()
        assert len(defs_via_class) == 7
        assert len(defs_via_instance) == 7


# ── Tests: No Rule 010 violations ─────────────────────────────────────────────


class TestRecommendDomainRestriction:
    """Rule 010 compliance — never recommends on user code/project."""

    async def test_never_refers_to_code(self, healthy_registry: ServiceRegistry) -> None:
        """Summary never mentions writing code, editing files, running tests."""
        coordinator = ApochCoordinator(healthy_registry)
        result = await coordinator.recommend()

        summary_lower = result["summary"].lower()
        explanation_lower = result["explanation"].lower()
        forbidden = ["código", "codigo", "archivo", "test", "tarea", "open code"]
        for word in forbidden:
            assert word not in summary_lower
            assert word not in explanation_lower
