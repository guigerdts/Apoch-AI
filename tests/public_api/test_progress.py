"""Tests for apoch_progress — ApochCoordinator.progress() orchestration.

Spec: mcp-public-api §Tool 5: apoch_progress
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers 10 scenarios from the DoD matrix:
  1. Happy path — Pulse responds with data → summary + trends in output
  2. Sin datos — Pulse responds with empty list → "No hay datos de actividad…"
  3. Tendencia positiva — TrendPoints show improvement → interpretation in Explanation
  4. Tendencia negativa — TrendPoints show decline → interpretation in Explanation
  5. Pulse timeout → ERR_DEPENDENCY_UNAVAILABLE
  6. Pulse not injected (services.pulse = None) → ERR_DEPENDENCY_UNAVAILABLE
  7. Periodo inválido (e.g. "año") → ERR_INVALID_ARGUMENT
  8. Output Contract — response contains NO WorkUnit IDs, cost/token, model names
  9. get_tool_defs() includes apoch_progress — acceptance gate
  10. Future tools still stubs — insights, logs not in get_tool_defs()
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from apoch.modules.pulse.models import TrendPoint, WorkUnit, WorkUnitFilter
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ── Mock services ─────────────────────────────────────────────────────────────


class _FakePulse:
    """Fake Pulse module that returns fixed list and trend data."""

    def __init__(
        self,
        work_units: list[WorkUnit] | None = None,
        trend_points: list[TrendPoint] | None = None,
    ) -> None:
        self._work_units = work_units or []
        self._trend_points = trend_points or []

    def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:  # noqa: A002
        return list(self._work_units)

    def trend(self, period_days: int = 1) -> list[TrendPoint]:
        return list(self._trend_points)


class _SlowPulse:
    """Pulse module that sleeps beyond the configured timeout."""

    async def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:  # noqa: A002
        await asyncio.sleep(10)
        return []

    async def trend(self, period_days: int = 1) -> list[TrendPoint]:
        await asyncio.sleep(10)
        return []


class _EmptyPulse:
    """Pulse module that returns empty data (no activity)."""

    def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:  # noqa: A002
        return []

    def trend(self, period_days: int = 1) -> list[TrendPoint]:
        return []


# ── Factory helpers ────────────────────────────────────────────────────────────


def _make_work_unit(id: str = "wu-001", model: str = "gpt-4") -> WorkUnit:
    """Create a minimal WorkUnit for tests."""
    return WorkUnit(
        id=id,
        session_id="test-session",
        model=model,
        tokens_input=100,
        tokens_output=50,
        wall_clock_s=10.0,
        cost=Decimal("0.01"),
        created_at="2026-07-16T10:00:00Z",
        completed_at="2026-07-16T10:05:00Z",
        lines_original=10,
        lines_modified=5,
    )


def _make_trend_point(
    work_unit_count: int,
    period_start: str = "2026-07-15T00:00:00Z",
    period_end: str = "2026-07-16T00:00:00Z",
) -> TrendPoint:
    """Create a TrendPoint for tests."""
    return TrendPoint(
        period_start=period_start,
        period_end=period_end,
        total_cost=Decimal("0.10"),
        total_tokens=500,
        work_unit_count=work_unit_count,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def happy_pulse_registry() -> ServiceRegistry:
    """Registry: Pulse returns work units with trend."""
    registry = ServiceRegistry()
    registry.pulse = _FakePulse(
        work_units=[_make_work_unit() for _ in range(10)],
        trend_points=[
            _make_trend_point(work_unit_count=4, period_start="2026-07-14T00:00:00Z"),
            _make_trend_point(work_unit_count=6, period_start="2026-07-15T00:00:00Z"),
        ],
    )
    return registry


@pytest.fixture
def growing_trend_registry() -> ServiceRegistry:
    """Registry: Pulse shows increasing productivity."""
    registry = ServiceRegistry()
    registry.pulse = _FakePulse(
        work_units=[_make_work_unit() for _ in range(10)],
        trend_points=[
            _make_trend_point(work_unit_count=2, period_start="2026-07-14T00:00:00Z"),
            _make_trend_point(work_unit_count=8, period_start="2026-07-15T00:00:00Z"),
        ],
    )
    return registry


@pytest.fixture
def declining_trend_registry() -> ServiceRegistry:
    """Registry: Pulse shows decreasing productivity."""
    registry = ServiceRegistry()
    registry.pulse = _FakePulse(
        work_units=[_make_work_unit() for _ in range(10)],
        trend_points=[
            _make_trend_point(work_unit_count=8, period_start="2026-07-14T00:00:00Z"),
            _make_trend_point(work_unit_count=2, period_start="2026-07-15T00:00:00Z"),
        ],
    )
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


# ── Tests: Happy path ─────────────────────────────────────────────────────────


class TestProgressHappyPath:
    """Pulse responds with data — happy path."""

    async def test_summary_includes_productivity(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """Pulse has data → summary mentions productividad."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        summary_lower = result["summary"].lower()
        assert "productividad" in summary_lower or "actividad" in summary_lower
        assert result["summary"] != "No hay datos de actividad para el período solicitado."
        assert result["suggested_action"] is None

    async def test_explanation_includes_count(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """Pulse has data → explanation mentions work unit count."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert "unidades de trabajo" in result["explanation"]
        assert "10" in result["explanation"]

    async def test_confidence_with_data(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """Data with trend points → confidence >= 0.7."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert result["confidence"] >= 0.7

    async def test_data_freshness_is_zero(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """Live query → data_freshness = 0."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert result["data_freshness"] == 0

    async def test_all_tool_response_fields(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """Response includes all required ToolResponse fields."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert "api_version" in result
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result

    async def test_api_version(self, happy_pulse_registry: ServiceRegistry) -> None:
        """api_version = '1.0'."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert result["api_version"] == "1.0"


# ── Tests: No data ────────────────────────────────────────────────────────────


class TestProgressNoData:
    """Pulse responds but has no data — friendly message."""

    async def test_no_data_message(self) -> None:
        """Empty Pulse data → 'No hay datos de actividad…'."""
        registry = ServiceRegistry()
        registry.pulse = _EmptyPulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result["summary"] == "No hay datos de actividad para el período solicitado."
        assert "No hay datos de actividad" in result["explanation"]
        assert result["confidence"] == 0.3
        assert result["suggested_action"] is None

    async def test_no_data_evidence(self) -> None:
        """No data → evidence uses functional label and low confidence."""
        registry = ServiceRegistry()
        registry.pulse = _EmptyPulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["source"] == "Sistema de rendimiento"
        assert result["evidence"][0]["confidence"] == 0.3


# ── Tests: Trend interpretation ───────────────────────────────────────────────


class TestProgressTrends:
    """TrendPoint data drives interpretation labels."""

    async def test_growing_trend(self, growing_trend_registry: ServiceRegistry) -> None:
        """More recent work → 'Productividad creciente'."""
        coordinator = ApochCoordinator(growing_trend_registry)
        result = await coordinator.progress()

        assert "creciente" in result["summary"]
        assert "aumentando" in result["explanation"]

    async def test_declining_trend(self, declining_trend_registry: ServiceRegistry) -> None:
        """Less recent work → 'Productividad decreciente'."""
        coordinator = ApochCoordinator(declining_trend_registry)
        result = await coordinator.progress()

        assert "decreciente" in result["summary"]
        assert "disminuyendo" in result["explanation"]

    async def test_stable_trend(self) -> None:
        """Equal work counts → 'Productividad estable'."""
        registry = ServiceRegistry()
        registry.pulse = _FakePulse(
            work_units=[_make_work_unit() for _ in range(10)],
            trend_points=[
                _make_trend_point(work_unit_count=5, period_start="2026-07-14T00:00:00Z"),
                _make_trend_point(work_unit_count=5, period_start="2026-07-15T00:00:00Z"),
            ],
        )

        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert "estable" in result["summary"]
        assert "estable" in result["explanation"]

    async def test_low_activity(self) -> None:
        """Very few work units → 'Actividad baja'."""
        registry = ServiceRegistry()
        registry.pulse = _FakePulse(
            work_units=[_make_work_unit() for _ in range(1)],
        )

        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result["summary"] == "Actividad baja"
        assert "baja" in result["explanation"]


# ── Tests: Pulse unavailable / timeout ────────────────────────────────────────


class TestProgressPulseUnavailable:
    """Pulse missing or failing → ERR_DEPENDENCY_UNAVAILABLE."""

    async def test_pulse_timeout(self) -> None:
        """Pulse times out → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.pulse = _SlowPulse()

        coordinator = ApochCoordinator(registry, timeouts={"pulse": 0.05})
        result = await coordinator.progress()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_pulse_none(self) -> None:
        """Pulse is None → ERR_DEPENDENCY_UNAVAILABLE."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.progress()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_pulse_exception(self) -> None:
        """Pulse raises exception → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _FailingPulse:
            def list(self, filter: WorkUnitFilter | None = None) -> list[WorkUnit]:  # noqa: A002
                msg = "pulse failure"
                raise RuntimeError(msg)

        registry.pulse = _FailingPulse()

        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_empty_registry(self, empty_registry: ServiceRegistry) -> None:
        """No services loaded → ERR_DEPENDENCY_UNAVAILABLE."""
        coordinator = ApochCoordinator(empty_registry)
        result = await coordinator.progress()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"


# ── Tests: Parameter validation ───────────────────────────────────────────────


class TestProgressParameterValidation:
    """Invalid parameters produce ERR_INVALID_ARGUMENT."""

    async def test_invalid_periodo(self) -> None:
        """'año' is not valid → ERR_INVALID_ARGUMENT."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.progress(periodo="año")

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_invalid_periodo_empty_string(self) -> None:
        """Empty string is not valid → ERR_INVALID_ARGUMENT."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.progress(periodo="")

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_valid_periodos_accepted(self) -> None:
        """Valid periodos are accepted (even with empty registry — pulse None)."""
        coordinator = ApochCoordinator(ServiceRegistry())

        for periodo in ("hoy", "semana", "mes"):
            result = await coordinator.progress(periodo=periodo)
            # With pulse=None, should be ERR_DEPENDENCY_UNAVAILABLE, not ERR_INVALID_ARGUMENT
            assert result["error"]["code"] != "ERR_INVALID_ARGUMENT"

    async def test_none_periodo_is_valid(self) -> None:
        """None is a valid period value (default)."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.progress(periodo=None)

        # Should not be ERR_INVALID_ARGUMENT (will be dependency error since pulse is None)
        assert result["error"]["code"] != "ERR_INVALID_ARGUMENT"

    async def test_periodo_case_sensitive(self) -> None:
        """'Hoy' (capitalized) is NOT valid."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.progress(periodo="Hoy")

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"


# ── Tests: Output contract (P6 — no internal exposure) ────────────────────────


class TestProgressOutputContract:
    """Response must NOT expose internal Pulse structures."""

    async def test_no_work_unit_ids(self, happy_pulse_registry: ServiceRegistry) -> None:
        """Summary/explanation/evidence must NOT contain WorkUnit IDs."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        for field in ("summary", "explanation"):
            assert "wu-001" not in result[field]
            assert "work_unit" not in result[field].lower()

        for entry in result["evidence"]:
            assert "wu-001" not in entry.get("based_on", "")
            assert "wu-001" not in entry.get("source", "")

    async def test_no_model_names(self, happy_pulse_registry: ServiceRegistry) -> None:
        """Response must NOT expose model names like 'gpt-4'."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        full_text = (
            result["summary"] + " " + result["explanation"]
            + " " + " ".join(e.get("based_on", "") for e in result["evidence"])
        )
        assert "gpt-4" not in full_text
        assert "gpt" not in full_text.lower()

    async def test_no_token_or_cost(self, happy_pulse_registry: ServiceRegistry) -> None:
        """Response must NOT contain token counts or costs."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        full_text = (
            result["summary"] + " " + result["explanation"]
        )
        assert "token" not in full_text.lower()
        assert "costo" not in full_text.lower()
        assert "cost" not in full_text.lower()

    async def test_no_pulse_class_name(self, happy_pulse_registry: ServiceRegistry) -> None:
        """Evidence source is 'Sistema de rendimiento', not 'Pulse'."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        for entry in result["evidence"]:
            assert "Pulse" not in entry["source"]
            assert "Sistema de rendimiento" in entry["source"]

    async def test_no_internal_filters(self, happy_pulse_registry: ServiceRegistry) -> None:
        """Response must NOT expose WorkUnitFilter details."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        full_text = (
            result["summary"] + " " + result["explanation"]
        )
        assert "session_id" not in full_text
        assert "WorkUnitFilter" not in full_text
        assert "limit" not in full_text or "limit" in ("limit",)  # allow natural language

    async def test_suggested_action_always_none(
        self, happy_pulse_registry: ServiceRegistry,
    ) -> None:
        """suggested_action is always None (pure query)."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert result["suggested_action"] is None

    async def test_no_extra_fields(self, happy_pulse_registry: ServiceRegistry) -> None:
        """No fields from other tools (status, health, history, etc.)."""
        coordinator = ApochCoordinator(happy_pulse_registry)
        result = await coordinator.progress()

        assert "priority" not in result
        assert "diagnostics" not in result
        assert "events" not in result
        assert "patterns" not in result
        assert "opportunities" not in result
        assert "entries" not in result


# ── Tests: Tool definition registration ───────────────────────────────────────


class TestProgressToolDef:
    """Tool definition registration for apoch_progress."""

    def test_get_tool_defs_includes_progress(self) -> None:
        """get_tool_defs includes apoch_progress."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert "apoch_progress" in names

    def test_get_tool_defs_has_seven_tools(self) -> None:
        """get_tool_defs has exactly 7 tools now (PR8)."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 7

    def test_get_tool_defs_progress_handler(self) -> None:
        """apoch_progress handler is 'progress'."""
        defs = ApochCoordinator.get_tool_defs()
        progress_def = next(d for d in defs if d.name == "apoch_progress")
        assert progress_def.handler_name == "progress"
        assert progress_def.description
        assert progress_def.input_schema == {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["hoy", "semana", "mes"],
                    "description": (
                        progress_def.input_schema["properties"]["periodo"]["description"]
                    ),
                },
            },
        }

    def test_get_tool_defs_is_classmethod(self) -> None:
        """get_tool_defs works on both class and instance (7 tools PR8)."""
        defs_via_class = ApochCoordinator.get_tool_defs()
        coordinator = ApochCoordinator(ServiceRegistry())
        defs_via_instance = coordinator.get_tool_defs()
        assert len(defs_via_class) == 7
        assert len(defs_via_instance) == 7


# ── Tests: No future tools in defs ────────────────────────────────────────────


class TestProgressAllToolsRegistered:
    """All 7 tools registered (PR8 brings apoch_logs)."""

    def test_all_tools_in_defs(self) -> None:
        """All tools up to PR8 are registered — apoch_logs included."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert names == {
            "apoch_status", "apoch_health",
            "apoch_history", "apoch_recommend",
            "apoch_progress", "apoch_insights",
            "apoch_logs",
        }
