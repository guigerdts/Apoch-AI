"""Integration tests for ApochCoordinator.progress() with REAL components.

Uses:
  - REAL PulseModule (from apoch.modules.pulse.module)
  - REAL PulseStore (from apoch.modules.pulse.storage) — in-memory dict backend
  - REAL WorkUnit, WorkUnitFilter, TrendPoint (from apoch.modules.pulse.models)
  - REAL Analysis (from apoch.modules.pulse.analysis) — via PulseModule.trend()
  - REAL Module/Context from apoch.core.module

Minimal fakes:
  - None for Pulse — PulseModule runs fully real with in-memory PulseStore.
  - No mocked methods on PulseModule at all.

Every WorkUnit is created via REAL PulseModule.record() from MeasurementInput.
Every TrendPoint comes from REAL PulseModule.trend() / Analysis.trend().
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apoch.core.module import Context
from apoch.modules.pulse.models import MeasurementInput
from apoch.modules.pulse.module import PulseModule
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ---------------------------------------------------------------------------
# Fixtures: REAL PulseModule
# ---------------------------------------------------------------------------


@pytest.fixture
def pulse_context() -> Context:
    """Minimal context with no cross-module services."""
    return Context()


@pytest.fixture
def real_pulse(pulse_context: Context) -> PulseModule:
    """A REAL PulseModule with in-memory PulseStore, started and ready.

    No SQLite — uses PulseStore's in-memory dict backend for speed and
    isolation.  All record(), list(), trend() methods are real.
    """
    mod = PulseModule({})
    # start() with no pulse_db_path → in-memory mode
    import asyncio

    asyncio.run(mod.start(pulse_context))
    return mod


def _seed_work_units(
    pulse: PulseModule,
    count: int,
    *,
    model: str = "gpt-4",
    tokens_input: int = 100,
    tokens_output: int = 50,
    wall_clock_s: float = 10.0,
    cost: Decimal | None = Decimal("0.01"),
    hours_ago: int = 1,
) -> None:
    """Seed *count* WorkUnits into *pulse* via REAL record().

    Each unit gets a deterministic ID and a created_at *hours_ago* from now.
    Tokens are bumped slightly per unit so trend aggregation yields
    distinct totals.
    """
    now = datetime.now(UTC)
    for i in range(count):
        ts = (now - timedelta(hours=hours_ago, minutes=i * 5)).isoformat()
        inp = MeasurementInput(
            session_id="integration-test",
            work_unit_id=f"int-wu-{hours_ago}-{i:04d}",
            model=model,
            tokens_input=tokens_input + i * 10,
            tokens_output=tokens_output + i * 5,
            wall_clock_s=wall_clock_s,
            cost=cost,
        )
        unit = pulse.record(inp)
        # Overwrite created_at so trend buckets align in the same window
        # We need to reach into the store to do this — PulseStore.save()
        # always sets created_at = now.  For trend tests we seed data with
        # specific timestamps via the store directly.
        object.__setattr__(unit, "created_at", ts)


def _seed_with_created_at(
    pulse: PulseModule,
    units: list[dict],
) -> None:
    """Seed WorkUnits with explicit created_at timestamps.

    *units* is a list of dicts with keys:
      - created_at (str, ISO 8601)
      - tokens_input (int)
      - tokens_output (int)
      - model (str, default "gpt-4")
      - id (str, optional — auto-generated if absent)
      - cost (Decimal | None)
    """
    for i, u in enumerate(units):
        inp = MeasurementInput(
            session_id="integration-test",
            work_unit_id=u.get("id", f"int-wu-ts-{i:04d}"),
            model=u.get("model", "gpt-4"),
            tokens_input=u.get("tokens_input", 100),
            tokens_output=u.get("tokens_output", 50),
            wall_clock_s=u.get("wall_clock_s", 10.0),
            cost=u.get("cost"),
        )
        unit = pulse.record(inp)
        object.__setattr__(unit, "created_at", u["created_at"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressIntegrationHappyPath:
    """PulseModule with real data — full pipeline verification."""

    async def test_progress_with_data(self, real_pulse: PulseModule) -> None:
        """Seed 10 work units → progress() returns summary with data."""
        _seed_work_units(real_pulse, count=10, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result["summary"] != "No hay datos de actividad para el período solicitado."
        assert "unidades de trabajo" in result["explanation"]
        assert "10" in result["explanation"]
        assert result["suggested_action"] is None
        assert result["data_freshness"] == 0
        assert result["api_version"] == "1.0"

    async def test_progress_confidence_with_data(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """Data exists → confidence is at least 0.5."""
        _seed_work_units(real_pulse, count=5, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        # Pulse has data but trend() may return < 2 buckets → confidence 0.5
        assert result["confidence"] in (0.5, 0.7)

    async def test_progress_evidence_structure(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """Evidence uses functional labels and fixed confidence."""
        _seed_work_units(real_pulse, count=5, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert len(result["evidence"]) == 1
        ev = result["evidence"][0]
        assert ev["source"] == "Sistema de rendimiento"
        assert ev["confidence"] == 0.8
        assert "based_on" in ev

    async def test_progress_response_contract(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """All ToolResponse fields present — no internal leaks."""
        _seed_work_units(real_pulse, count=3, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert set(result.keys()) == {
            "api_version",
            "summary",
            "explanation",
            "evidence",
            "suggested_action",
            "confidence",
            "generated_at",
            "data_freshness",
            "metadata",
        }
        # P6: no internal structure leaks
        assert result["metadata"] == {}


class TestProgressIntegrationNoData:
    """PulseModule started but empty — handles gracefully."""

    async def test_progress_no_data(self, real_pulse: PulseModule) -> None:
        """Empty Pulse → 'No hay datos de actividad' + confidence 0.3."""
        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result["summary"] == "No hay datos de actividad para el período solicitado."
        assert result["confidence"] == 0.3
        assert result["suggested_action"] is None
        assert result["data_freshness"] == 0
        assert result["metadata"] == {}

    async def test_progress_no_data_evidence(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """Empty Pulse → evidence with based_on='0 unidades de trabajo'."""
        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert len(result["evidence"]) == 1
        ev = result["evidence"][0]
        assert ev["source"] == "Sistema de rendimiento"
        assert ev["confidence"] == 0.3
        assert "0 unidades" in ev["based_on"]


class TestProgressIntegrationTrends:
    """Trend via REAL Analysis.trend() from real work units."""

    async def test_growing_trend(self, real_pulse: PulseModule) -> None:
        """More work in recent period → 'Productividad creciente'.

        Data must span MORE than trend_window (3d for 'semana') so
        Analysis.trend() creates 2+ buckets and _interpret_progress_trend
        can compare them.
        """
        now = datetime.now(UTC)
        _seed_with_created_at(
            real_pulse,
            [
                # Period 1: 2 units (4 days ago — bucket 1)
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                # Period 2: 5 units (now — bucket 2, growing)
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
            ],
        )

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress(periodo="semana")

        assert "creciente" in result["summary"] or "aumentando" in result["explanation"]

    async def test_declining_trend(self, real_pulse: PulseModule) -> None:
        """Less work in recent period → 'Productividad decreciente'.

        Data must span MORE than trend_window (3d for 'semana') so
        Analysis.trend() creates 2+ buckets.
        """
        now = datetime.now(UTC)
        _seed_with_created_at(
            real_pulse,
            [
                # Period 1: 5 units (4 days ago — bucket 1)
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                # Period 2: 2 units (now — bucket 2, declining)
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
            ],
        )

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress(periodo="semana")

        assert "decreciente" in result["summary"] or "disminuyendo" in result["explanation"]

    async def test_low_activity_trend(self, real_pulse: PulseModule) -> None:
        """Very few units → 'Actividad baja' regardless of trend."""
        _seed_work_units(real_pulse, count=1, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert "baja" in result["summary"].lower()

    async def test_confidence_rises_with_trend(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """Data + 2+ trend buckets → confidence 0.7.

        Need data spanning MORE than trend_window (3d for 'semana')
        to get 2+ buckets from Analysis.trend().
        """
        now = datetime.now(UTC)
        _seed_with_created_at(
            real_pulse,
            [
                {"created_at": (now - timedelta(days=7)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(days=4)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=1)).isoformat(), "tokens_input": 100},
            ],
        )

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress(periodo="semana")

        # 3 units across 7 days spanning 3+ trend buckets → confidence 0.7
        assert result["confidence"] == 0.7


class TestProgressIntegrationErrors:
    """Error paths — Pulse unavailable, invalid params."""

    async def test_no_pulse_module(self) -> None:
        """Pulse=None → ERR_DEPENDENCY_UNAVAILABLE (error envelope)."""
        registry = ServiceRegistry()  # pulse is None by default
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()

        assert result.get("ok") is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"
        # Error responses use the flat error envelope — no suggested_action
        assert "suggested_action" not in result

    async def test_invalid_periodo(self, real_pulse: PulseModule) -> None:
        """Periodo='año' → ERR_INVALID_ARGUMENT."""
        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress(periodo="año")

        assert "error" in result
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"


class TestProgressIntegrationPeriodos:
    """Parameterised periodos — hoy, semana, mes."""

    @pytest.mark.parametrize("periodo", ["hoy", "semana", "mes"])
    async def test_valid_periodos(
        self,
        real_pulse: PulseModule,
        periodo: str,
    ) -> None:
        """All valid periodos work without error."""
        _seed_work_units(real_pulse, count=5, hours_ago=2)

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress(periodo=periodo)

        assert "error" not in result
        assert result["suggested_action"] is None
        assert result["data_freshness"] == 0

    async def test_default_periodo_equals_24h(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """periodo=None → queries last 24 hours (same as default)."""
        now = datetime.now(UTC)
        # Data inside 24h window
        _seed_with_created_at(
            real_pulse,
            [
                {"created_at": (now - timedelta(hours=2)).isoformat(), "tokens_input": 100},
                {"created_at": (now - timedelta(hours=10)).isoformat(), "tokens_input": 200},
            ],
        )
        # Data outside 24h window (use unique IDs with id field)
        _seed_with_created_at(
            real_pulse,
            [
                {
                    "id": "int-wu-outside-000",
                    "created_at": (now - timedelta(hours=48)).isoformat(),
                    "tokens_input": 300,
                },
            ],
        )

        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.progress()  # periodo=None

        assert "error" not in result
        # Only the 2 inside-window units should count
        assert "2" in result["explanation"]


class TestProgressIntegrationFreshnessAndAction:
    """Invariant checks on data_freshness and suggested_action."""

    async def test_data_freshness_always_zero(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """data_freshness is always 0 (live query, no cache)."""
        _seed_work_units(real_pulse, count=3, hours_ago=1)
        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)

        result = await coordinator.progress()
        assert result["data_freshness"] == 0

        result = await coordinator.progress(periodo="hoy")
        assert result["data_freshness"] == 0

        result = await coordinator.progress(periodo="semana")
        assert result["data_freshness"] == 0

    async def test_suggested_action_always_none(
        self,
        real_pulse: PulseModule,
    ) -> None:
        """suggested_action is always None (pure query tool)."""
        _seed_work_units(real_pulse, count=3, hours_ago=1)
        registry = ServiceRegistry(pulse=real_pulse)
        coordinator = ApochCoordinator(registry)

        # With data
        result = await coordinator.progress()
        assert result["suggested_action"] is None

        # No data
        empty_registry = ServiceRegistry(pulse=PulseModule({}))
        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, lambda: None)
        # Start a fresh empty PulseModule
        empty_pulse = PulseModule({})
        await empty_pulse.start(Context())
        empty_registry.pulse = empty_pulse
        result2 = await ApochCoordinator(empty_registry).progress()
        assert result2["suggested_action"] is None

        # No Pulse
        result3 = await ApochCoordinator(ServiceRegistry()).progress()
        assert result3.get("suggested_action") is None
