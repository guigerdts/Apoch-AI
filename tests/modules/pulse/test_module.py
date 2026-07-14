"""Tests for PulseModule — lifecycle and measurement orchestration.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §File Changes
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from apoch.core.module import Context, ModuleState
from apoch.modules.pulse.models import MeasurementInput, WorkUnitFilter
from apoch.modules.pulse.module import PulseModule


@pytest.fixture
def config() -> dict:
    return {}


@pytest.fixture
def context() -> Context:
    return Context()


class TestLifecycle:
    """PulseModule lifecycle (Chronicle pattern)."""

    async def test_initial_state_is_loaded(self, config: dict) -> None:
        mod = PulseModule(config)
        assert mod.state == ModuleState.LOADED

    async def test_start_transitions_to_running(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        assert mod.state == ModuleState.RUNNING

    async def test_stop_transitions_to_stopped(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        await mod.stop()
        assert mod.state == ModuleState.STOPPED

    async def test_shutdown_transitions_to_shutdown(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        await mod.stop()
        await mod.shutdown()
        assert mod.state == ModuleState.SHUTDOWN

    async def test_full_lifecycle(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        assert mod.state == ModuleState.LOADED
        await mod.start(context)
        assert mod.state == ModuleState.RUNNING
        await mod.stop()
        assert mod.state == ModuleState.STOPPED
        await mod.shutdown()
        assert mod.state == ModuleState.SHUTDOWN

    async def test_idempotent_stop_does_not_raise(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        await mod.stop()
        await mod.stop()  # Second stop — must not raise
        assert mod.state == ModuleState.STOPPED


class TestMeasurement:
    """PulseModule measurement orchestration."""

    async def test_record_returns_work_unit(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert unit.id == "wu-1"
        assert unit.model == "claude-4"
        assert unit.cost is None

    async def test_record_with_cost(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.015"),
        ))
        assert unit.cost == Decimal("0.015")

    async def test_get_returns_stored_unit(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        unit = mod.get("wu-1")
        assert unit is not None
        assert unit.session_id == "s1"

    async def test_get_returns_none_for_unknown(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        assert mod.get("nonexistent") is None

    async def test_list_returns_all(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        for i in range(3):
            mod.record(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        assert len(mod.list()) == 3

    async def test_count_after_records(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert mod.count() == 1

    async def test_end_to_end_flow(
        self, config: dict, context: Context,
    ) -> None:
        """Record → get → list → count — complete measurement path."""
        mod = PulseModule(config)
        await mod.start(context)

        # Record two measurements
        m1 = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-a", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        m2 = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-b", model="gpt-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
            cost=Decimal("0.030"),
        ))

        # Get by ID
        assert mod.get("wu-a") is m1
        assert mod.get("wu-b") is m2

        # List all
        assert len(mod.list()) == 2

        # Count
        assert mod.count() == 2
        assert mod.count(WorkUnitFilter(model="claude-4")) == 1


class TestAnalysis:
    """PulseModule exposes read-only analysis methods."""

    async def test_productivity_summary(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.015"),
        ))
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="claude-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
            cost=Decimal("0.030"),
        ))
        s = mod.productivity_summary()
        assert s.total_work_units == 2
        assert s.total_tokens_input == 300
        assert s.total_tokens_output == 150
        assert s.total_cost == Decimal("0.045")
        assert s.avg_cost_per_unit == Decimal("0.0225")
        assert s.avg_time_per_unit == 45.0

    async def test_trend(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        points = mod.trend()
        assert len(points) == 1
        assert points[0].work_unit_count == 1

    async def test_rework_rate_zero_for_single(
        self, config: dict, context: Context,
    ) -> None:
        mod = PulseModule(config)
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert mod.rework_rate() == 0.0

    async def test_no_forbidden_methods(
        self, config: dict, context: Context,
    ) -> None:
        """PulseModule MUST NOT expose methods it doesn't own."""
        mod = PulseModule(config)
        await mod.start(context)
        assert not hasattr(mod, "aggregate")
        assert not hasattr(mod, "optimize")
        assert not hasattr(mod, "recommend")


class TestCostCalculation:
    """PulseModule.record() MUST calculate cost from pricing config (R2)."""

    async def test_cost_calculated_from_pricing(self, context: Context) -> None:
        """GIVEN pricing config WHEN cost is None THEN cost = tokens × price."""
        pricing = {"claude-4": Decimal("0.00001")}
        mod = PulseModule({"model_pricing": pricing})
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=None,
        ))
        # (100 + 50) × 0.00001 = 0.0015
        assert unit.cost == Decimal("0.0015")

    async def test_explicit_cost_passthrough(self, context: Context) -> None:
        """GIVEN explicit cost WHEN recorded THEN cost is used as-is."""
        pricing = {"claude-4": Decimal("0.00001")}
        mod = PulseModule({"model_pricing": pricing})
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.9999"),  # explicit override
        ))
        assert unit.cost == Decimal("0.9999")

    async def test_missing_price_logs_warning(
        self, context: Context, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GIVEN no price for model WHEN cost is None THEN warning logged."""
        import logging
        caplog.set_level(logging.WARNING)
        pricing = {"some-other-model": Decimal("0.00001")}
        mod = PulseModule({"model_pricing": pricing})
        await mod.start(context)
        mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=None,
        ))
        assert "No price configured for model 'claude-4'" in caplog.text

    async def test_missing_price_cost_stays_none(self, context: Context) -> None:
        """GIVEN no price for model WHEN cost is None THEN cost stays None."""
        pricing = {"some-other-model": Decimal("0.00001")}
        mod = PulseModule({"model_pricing": pricing})
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=None,
        ))
        assert unit.cost is None

    async def test_no_pricing_config_no_cost(self, context: Context) -> None:
        """GIVEN no model_pricing config WHEN cost is None THEN cost stays None."""
        mod = PulseModule({})
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=None,
        ))
        assert unit.cost is None

    async def test_cost_with_zero_tokens(self, context: Context) -> None:
        """GIVEN pricing config WHEN zero tokens THEN cost is 0."""
        pricing = {"claude-4": Decimal("0.00001")}
        mod = PulseModule({"model_pricing": pricing})
        await mod.start(context)
        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=0, tokens_output=0, wall_clock_s=30.0,
            cost=None,
        ))
        assert unit.cost == Decimal("0")


class TestSqliteLifecycle:
    """PulseModule lifecycle with SQLite persistence (R10)."""

    async def test_start_opens_sqlite(self, tmp_path: Path, context: Context) -> None:
        """start() MUST create a SQLite database and pass it to PulseStore."""
        db_path = tmp_path / "pulse.db"
        mod = PulseModule({"pulse_db_path": str(db_path)})
        await mod.start(context)
        # Verify the file was created
        assert db_path.exists()
        # Verify PulseStore has a SQLite connection
        assert mod._store is not None
        assert mod._store._conn is not None
        # Verify schema was initialised
        tables = mod._store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        assert "work_units" in names
        await mod.stop()

    async def test_stop_closes_connection(self, tmp_path: Path, context: Context) -> None:
        """stop() MUST close the SQLite connection."""
        db_path = tmp_path / "pulse.db"
        mod = PulseModule({"pulse_db_path": str(db_path)})
        await mod.start(context)
        conn = mod._store._conn
        assert conn is not None
        await mod.stop()
        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    async def test_end_to_end_with_sqlite(self, tmp_path: Path, context: Context) -> None:
        """Record → list → get with SQLite persistence via PulseModule."""
        db_path = tmp_path / "pulse.db"
        mod = PulseModule({"pulse_db_path": str(db_path)})
        await mod.start(context)

        unit = mod.record(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert unit.id == "wu-1"
        assert mod.count() == 1
        assert mod.get("wu-1") is not None
        await mod.stop()

    async def test_in_memory_when_no_db_path(self, config: dict, context: Context) -> None:
        """start() MUST use in-memory PulseStore when pulse_db_path is not set."""
        mod = PulseModule(config)
        await mod.start(context)
        assert mod._store is not None
        assert mod._store._conn is None
        await mod.stop()


class TestCrossModuleServices:
    """PulseModule exposes duck-typed cross-module services."""

    async def test_services_property_exists(
        self, config: dict, context: Context,
    ) -> None:
        """PulseModule MUST expose a @property services."""
        mod = PulseModule(config)
        await mod.start(context)
        svc = mod.services
        assert isinstance(svc, dict)

    async def test_services_contains_pulse_measurements(
        self, config: dict, context: Context,
    ) -> None:
        """services MUST include the 'pulse.measurements' key."""
        mod = PulseModule(config)
        await mod.start(context)
        assert "pulse.measurements" in mod.services

    async def test_pulse_measurements_is_list_method(
        self, config: dict, context: Context,
    ) -> None:
        """'pulse.measurements' MUST delegate to PulseModule.list."""
        mod = PulseModule(config)
        await mod.start(context)
        # Both return the same data for the same query
        assert mod.services["pulse.measurements"]() == mod.list()

    async def test_service_discovery_via_registry(
        self, config: dict, context: Context,
    ) -> None:
        """ModuleRegistry MUST discover pulse.measurements via start_all()."""
        from apoch.core.registry import ModuleRegistry

        mod = PulseModule(config)
        await mod.start(context)
        reg = ModuleRegistry()
        reg._loaded["pulse"] = mod
        reg._init_order.append("pulse")
        await reg.start_all(context)
        assert "pulse.measurements" in context.services

    async def test_entry_point_resolution(self) -> None:
        """PulseModule MUST be discoverable via entry point group."""
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.modules", name="pulse")
        assert len(eps) == 1, f"Expected 1 entry point, got {len(eps)}"
        # EntryPoints supports iteration — get first (and only) entry
        ep = next(iter(eps))
        cls = ep.load()
        assert cls is PulseModule
