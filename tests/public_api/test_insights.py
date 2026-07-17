"""Tests for apoch_insights — ApochCoordinator.insights() orchestration.

Spec: mcp-public-api §Tool 6: apoch_insights
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers 11+ scenarios from the DoD matrix:
  1. Happy path — Optimizer with patterns + Pulse responds
  2. Pulse timeout — Optimizer OK, Pulse no responde → respuesta válida confidence 0.7
  3. Pulse no disponible — services.pulse = None → respuesta válida confidence 0.5
  4. Sin patterns — Optimizer responde sin type=pattern → "No se detectaron patrones…"
  5. Solo anomalies/opportunities → misma respuesta
  6. Optimizer timeout → ERR_DEPENDENCY_UNAVAILABLE
  7. Optimizer no inyectado (None) → ERR_DEPENDENCY_UNAVAILABLE
  8. Output contract — NO evidence dict, mean, std, tokens, cost, names
  9. get_tool_defs() registra exactamente 6 tools
  10. apoch_logs NO está en get_tool_defs()
  11. Confidence formula — verificar cálculo exacto
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

from __future__ import annotations

import asyncio

import pytest

from apoch.modules.optimizer.models import OptimizationHypothesis
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ── Hypothesis factory ──────────────────────────────────────────────────────────


def _make_hypothesis(
    type_: str = "pattern",
    domain: str = "time",
    confidence: float = 0.85,
    affected_scope: str = "Sesiones largas del editor",
    evidence: dict | None = None,
) -> OptimizationHypothesis:
    """Create a minimal OptimizationHypothesis for tests.

    The evidence dict contains internal stats that MUST NOT leak into
    the public response.
    """
    return OptimizationHypothesis(
        type=type_,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        confidence=confidence,
        evidence=evidence or {"mean": 42.5, "std": 12.3, "count": 50},
        affected_scope=affected_scope,
        generated_at="2026-07-16T10:00:00Z",
    )


# ── Mock services ─────────────────────────────────────────────────────────────


class _FakeOptimizer:
    """Fake Optimizer that returns a fixed list of hypotheses."""

    def __init__(self, hypotheses: list[OptimizationHypothesis] | None = None) -> None:
        self._hypotheses = hypotheses or []

    @property
    def services(self) -> dict:
        return {"optimizer.hypotheses": lambda: list(self._hypotheses)}


class _SlowOptimizer:
    """Optimizer that sleeps beyond the configured timeout."""

    @property
    def services(self) -> dict:
        async def _slow() -> list:
            await asyncio.sleep(10)
            return []

        return {"optimizer.hypotheses": _slow}


class _FakePulse:
    """Fake Pulse module that returns a fixed list of work units."""

    def __init__(self, work_units: list | None = None) -> None:
        self._work_units = work_units or []

    def list(self) -> list:
        return list(self._work_units)


class _SlowPulse:
    """Pulse module that sleeps beyond the configured timeout."""

    async def list(self) -> list:
        await asyncio.sleep(10)
        return []


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def happy_registry() -> ServiceRegistry:
    """Registry: Optimizer with patterns + Pulse with data."""
    registry = ServiceRegistry()
    registry.optimizer = _FakeOptimizer(hypotheses=[
        _make_hypothesis(
            type_="pattern",
            domain="time",
            confidence=0.85,
            affected_scope="Sesiones largas del editor",
        ),
        _make_hypothesis(
            type_="pattern",
            domain="cost",
            confidence=0.72,
            affected_scope="múltiples ventanas abiertas",
        ),
    ])
    registry.pulse = _FakePulse(work_units=["wu-1", "wu-2", "wu-3"])
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


# ── Tests: Happy path ─────────────────────────────────────────────────────────


class TestInsightsHappyPath:
    """Optimizer with patterns + Pulse responds."""

    async def test_summary_includes_pattern_count(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Two patterns → summary mentions '2 patrones'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert "2 patrones" in result["summary"]
        assert "productividad" in result["summary"]

    async def test_explanation_has_one_line_per_pattern(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Two hypotheses → two lines in explanation."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        lines = result["explanation"].split("\n")
        assert len(lines) == 2
        assert "Sesiones largas del editor" in lines[0]
        assert "múltiples ventanas abiertas" in lines[1]

    async def test_explanation_uses_natural_language(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Explanation uses natural language with 'Detecté un patrón'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert "Detecté un patrón en" in result["explanation"]

    async def test_confidence_happy_path(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Happy path → confidence = hypothesis_avg * 1.0."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        # hypothesis_avg = (0.85 + 0.72) / 2 = 0.785
        # pulse_factor = 1.0 (Pulse OK)
        # confidence = round(0.785 * 1.0, 2) = 0.78 (Python banker's rounding)
        assert result["confidence"] == 0.78

    async def test_suggested_action_is_none(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """suggested_action is always None."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert result["suggested_action"] is None

    async def test_all_tool_response_fields(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Response includes all required ToolResponse fields."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert "api_version" in result
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result

    async def test_api_version(self, happy_registry: ServiceRegistry) -> None:
        """api_version = '1.0'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert result["api_version"] == "1.0"

    async def test_data_freshness_is_zero(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Fresh query → data_freshness = 0."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.insights()

        assert result["data_freshness"] == 0


# ── Tests: Pulse degraded modes ───────────────────────────────────────────────


class TestInsightsPulseDegraded:
    """Pulse unavailable or timeout → valid response with degraded confidence."""

    async def test_pulse_timeout(self) -> None:
        """Pulse times out → response with confidence factor 0.7."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", confidence=0.80),
        ])
        registry.pulse = _SlowPulse()

        coordinator = ApochCoordinator(registry, timeouts={"pulse": 0.05})
        result = await coordinator.insights()

        # Not an error — valid response
        assert "ok" not in result
        assert "error" not in result

        # hypothesis_avg = 0.80, pulse_factor = 0.7
        # confidence = round(0.80 * 0.7, 2) = 0.56
        assert result["confidence"] == pytest.approx(0.56, abs=0.01)
        assert "patrones" in result["summary"]

    async def test_pulse_not_available(self) -> None:
        """No Pulse injected → response with confidence factor 0.5."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", confidence=0.80),
        ])
        # pulse is None by default

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        # Valid response, not error
        assert "ok" not in result
        assert "error" not in result

        # hypothesis_avg = 0.80, pulse_factor = 0.5
        # confidence = round(0.80 * 0.5, 2) = 0.40
        assert result["confidence"] == pytest.approx(0.40, abs=0.01)
        assert "patrones" in result["summary"]

    async def test_pulse_timeout_still_has_evidence(
        self,
    ) -> None:
        """Pulse timeout → evidence includes Sistema de optimización only."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _SlowPulse()

        coordinator = ApochCoordinator(registry, timeouts={"pulse": 0.05})
        result = await coordinator.insights()

        assert len(result["evidence"]) >= 1
        # Sistema de optimización should be present
        sources = {e["source"] for e in result["evidence"]}
        assert "Sistema de optimización" in sources
        # Pulse timed out → Sistema de rendimiento should NOT be present
        assert "Sistema de rendimiento" not in sources


# ── Tests: No patterns ────────────────────────────────────────────────────────


class TestInsightsNoPatterns:
    """Optimizer has no type=pattern hypotheses."""

    async def test_no_patterns_in_optimizer(self) -> None:
        """Optimizer returns empty list → no patterns summary."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[])
        registry.pulse = _FakePulse(work_units=["wu-1"])

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert result["summary"] == "No se detectaron patrones ni oportunidades de mejora."
        assert result["confidence"] == 0.0
        assert result["suggested_action"] is None

    async def test_only_anomalies_and_opportunities(self) -> None:
        """Hypotheses exist but none are type=pattern → same response."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="opportunity", domain="time",
                             affected_scope="reducir pestañas abiertas"),
            _make_hypothesis(type_="anomaly", domain="cost",
                             affected_scope="pico inusual en costos"),
        ])
        registry.pulse = _FakePulse(work_units=["wu-1"])

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert result["summary"] == "No se detectaron patrones ni oportunidades de mejora."
        assert result["confidence"] == 0.0
        # No error — this is a valid response
        assert "ok" not in result

    async def test_no_patterns_not_an_error(self) -> None:
        """No patterns is a valid response, NOT an error."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert "ok" not in result
        assert "error" not in result


# ── Tests: Optimizer unavailable ──────────────────────────────────────────────


class TestInsightsOptimizerUnavailable:
    """Optimizer missing or failing → ERR_DEPENDENCY_UNAVAILABLE."""

    async def test_optimizer_timeout(self) -> None:
        """Optimizer times out → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.optimizer = _SlowOptimizer()
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry, timeouts={"optimizer": 0.05})
        result = await coordinator.insights()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_optimizer_not_injected(self) -> None:
        """Optimizer is None → ERR_DEPENDENCY_UNAVAILABLE."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.insights()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_optimizer_no_services_attr(self) -> None:
        """Optimizer lacks services attribute → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _NoServicesOptimizer:  # noqa: F841
            pass

        registry.optimizer = _NoServicesOptimizer()
        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_optimizer_no_hypotheses_service(self) -> None:
        """Optimizer services lacks 'optimizer.hypotheses' → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _EmptyServicesOptimizer:
            @property
            def services(self) -> dict:
                return {}

        registry.optimizer = _EmptyServicesOptimizer()
        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"


# ── Tests: Output contract (P6 — no internal exposure) ────────────────────────


class TestInsightsOutputContract:
    """Response must NOT expose internal Optimizer/Pulse structures."""

    async def test_no_evidence_dict_in_response(self) -> None:
        """Response must NOT contain evidence dict from OptimizationHypothesis."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", domain="time",
                             evidence={"mean": 42.5, "std": 12.3}),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        full_text = result["summary"] + " " + result["explanation"]
        # These internal metrics must NOT leak
        assert "mean" not in full_text
        assert "42.5" not in full_text
        assert "std" not in full_text
        assert "12.3" not in full_text

    async def test_no_tokens_or_cost(self) -> None:
        """Response must NOT contain token counts or costs."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        full_text = result["summary"] + " " + result["explanation"]
        assert "token" not in full_text.lower()
        assert "costo" not in full_text.lower()
        assert "cost" not in full_text.lower()

    async def test_no_module_names_in_evidence(self) -> None:
        """Evidence uses functional labels, not module names."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _FakePulse(work_units=["wu-1"])

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        for entry in result["evidence"]:
            assert "Optimizer" not in entry["source"]
            assert "Pulse" not in entry["source"]
            assert entry["source"] in (
                "Sistema de optimización", "Sistema de rendimiento",
            )

    async def test_no_optimization_hypothesis_class_name(self) -> None:
        """Response must not mention OptimizationHypothesis."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        full_text = result["summary"] + " " + result["explanation"]
        assert "OptimizationHypothesis" not in full_text

    async def test_no_detector_names(self) -> None:
        """Response must not contain internal detector names."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        full_text = result["summary"] + " " + result["explanation"]
        detector_names = [
            "BaselineGenerator", "DegradationDetector",
            "SessionPatternDetector", "ModelEfficiencyDetector",
            "AnomalyDetector", "ReworkCorrelationDetector",
        ]
        for name in detector_names:
            assert name not in full_text

    async def test_no_internal_fields_in_explanation(self) -> None:
        """Explanation does not contain evidence keys, count, min, max."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", domain="time",
                             evidence={"min": 10, "max": 100, "count": 50}),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        expl = result["explanation"]
        assert "min" not in expl
        assert "max" not in expl
        assert "count" not in expl

    async def test_no_extra_fields_from_other_tools(self) -> None:
        """Response has no fields from other tools."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern"),
        ])
        registry.pulse = _FakePulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        assert "priority" not in result
        assert "diagnostics" not in result
        assert "events" not in result
        assert "entries" not in result


# ── Tests: Confidence formula exact calculation ────────────────────────────────


class TestInsightsConfidenceFormula:
    """Confidence formula: round(hypothesis_avg * pulse_factor, 2)."""

    async def test_single_hypothesis_optimizer_only(self) -> None:
        """One hypothesis at 0.85, no Pulse → 0.85 * 0.5 = 0.43."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", confidence=0.85),
        ])
        # pulse is None

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        # hypothesis_avg = 0.85, pulse_factor = 0.5
        # confidence = round(0.85 * 0.5, 2) = round(0.425, 2) = 0.42
        assert result["confidence"] == pytest.approx(0.42, abs=0.01)

    async def test_multiple_hypotheses_avg(self) -> None:
        """Two hypotheses avg (0.85 + 0.65) / 2 * 1.0 = 0.75."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", confidence=0.85),
            _make_hypothesis(type_="pattern", confidence=0.65),
        ])
        registry.pulse = _FakePulse(work_units=["wu-1"])

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        # hypothesis_avg = 0.75, pulse_factor = 1.0
        assert result["confidence"] == 0.75

    async def test_rounding_two_decimals(self) -> None:
        """Confidence is rounded to 2 decimal places."""
        registry = ServiceRegistry()
        registry.optimizer = _FakeOptimizer(hypotheses=[
            _make_hypothesis(type_="pattern", confidence=0.777),
        ])
        registry.pulse = _FakePulse(work_units=["wu-1"])

        coordinator = ApochCoordinator(registry)
        result = await coordinator.insights()

        # confidence = round(0.777 * 1.0, 2) = 0.78
        assert result["confidence"] == 0.78


# ── Tests: Tool definition registration ───────────────────────────────────────


class TestInsightsToolDef:
    """Tool definition registration for apoch_insights."""

    def test_get_tool_defs_includes_insights(self) -> None:
        """get_tool_defs includes apoch_insights."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert "apoch_insights" in names

    def test_get_tool_defs_has_seven_tools(self) -> None:
        """get_tool_defs has exactly 7 tools now (PR8)."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 7

    def test_get_tool_defs_insights_handler(self) -> None:
        """apoch_insights handler is 'insights'."""
        defs = ApochCoordinator.get_tool_defs()
        insights_def = next(d for d in defs if d.name == "apoch_insights")
        assert insights_def.handler_name == "insights"
        assert insights_def.description
        assert insights_def.input_schema == {"type": "object", "properties": {}}

    def test_get_tool_defs_is_classmethod(self) -> None:
        """get_tool_defs works on both class and instance (7 tools PR8)."""
        defs_via_class = ApochCoordinator.get_tool_defs()
        coordinator = ApochCoordinator(ServiceRegistry())
        defs_via_instance = coordinator.get_tool_defs()
        assert len(defs_via_class) == 7
        assert len(defs_via_instance) == 7


class TestInsightsAllToolsRegistered:
    """All 7 tools registered (PR8 brings apoch_logs)."""

    def test_apoch_logs_in_defs(self) -> None:
        """apoch_logs IS in get_tool_defs (PR8 implemented)."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert "apoch_logs" in names

    def test_all_seven_tools_in_defs(self) -> None:
        """get_tool_defs has exactly these 7 tools."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert names == {
            "apoch_status", "apoch_health",
            "apoch_history", "apoch_recommend",
            "apoch_progress", "apoch_insights",
            "apoch_logs",
        }
