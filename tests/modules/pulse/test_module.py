"""Tests for PulseModule — lifecycle and measurement orchestration.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §File Changes
"""

from __future__ import annotations

from decimal import Decimal

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
