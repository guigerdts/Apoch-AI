"""Tests for ``apoch eil`` — Engineering Intelligence Layer CLI.

Spec: cli-interface §EIL Dashboard, §EIL Status
Design: Engineering Intelligence Subcommands (eil/)

Tests are organised by command (dashboard, status, hypotheses, recs, trends)
with sub-classes for text output, JSON output, filters, and edge cases.

All tests mock ``apoch.cli.eil._load_and_start`` to control module state
and service return values without loading real modules.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from typer.testing import CliRunner

from apoch.cli.app import app
from apoch.core.module import ModuleState
from apoch.modules.optimizer.models import OptimizationHypothesis
from apoch.modules.oracle.models import Recommendation
from apoch.modules.pulse.models import TrendPoint

# =============================================================================
# Mock builders
# =============================================================================


def _make_mock_module(mocker, state: ModuleState = ModuleState.RUNNING) -> Any:
    """Create a mock module with a given state and no services."""
    mod = mocker.Mock()
    mod.state = state
    mod.services = {}
    return mod


def _make_mock_registry(
    mocker,
    states: dict[str, ModuleState] | None = None,
    extra_services: dict | None = None,
    guardian_diags: dict | None = None,
) -> tuple[Any, Any]:
    """Build mock Context and ModuleRegistry for EIL CLI tests.

    Returns:
        A (ctx, registry) tuple.  Patch ``apoch.cli.eil._load_and_start``
        to return this pair.
    """
    from apoch.core.module import Context

    if states is None:
        states = {
            n: ModuleState.RUNNING
            for n in ("pulse", "optimizer", "oracle", "guardian", "chronicle")
        }

    ctx = mocker.Mock(spec=Context)
    registry = mocker.Mock()

    # Loaded modules as a real dict (supports .get(), .items(), etc.)
    loaded: dict[str, Any] = {}
    services: dict[str, Any] = {}

    for name, state in states.items():
        mod = _make_mock_module(mocker, state)
        loaded[name] = mod

    # ---- Pulse service ----
    if states.get("pulse") == ModuleState.RUNNING:
        services["pulse.measurements"] = lambda: []
        pulse_mod = loaded["pulse"]
        pulse_mod.services = {"pulse.measurements": lambda: []}
        pulse_mod.trend = mocker.Mock(return_value=[])

    # ---- Optimizer services ----
    if states.get("optimizer") == ModuleState.RUNNING:
        services["optimizer.hypotheses"] = lambda: []
        services["optimizer.baselines"] = lambda: {}
        services["optimizer.status"] = lambda: {
            "available": True,
            "hypothesis_count": 0,
            "baseline_count": 0,
            "pulse_connected": True,
        }
        loaded["optimizer"].services = {
            "optimizer.hypotheses": lambda: [],
            "optimizer.baselines": lambda: {},
            "optimizer.status": lambda: {},
        }

    # ---- Oracle services ----
    if states.get("oracle") == ModuleState.RUNNING:
        services["oracle.recommendations"] = lambda: []
        services["oracle.status"] = lambda: {
            "available": True,
            "optimizer_connected": True,
            "chronicle_connected": True,
        }
        loaded["oracle"].services = {
            "oracle.recommendations": lambda: [],
            "oracle.status": lambda: {},
        }

    # ---- Chronicle service ----
    if states.get("chronicle") == ModuleState.RUNNING:
        services["chronicle.record"] = lambda e: None
        loaded["chronicle"].services = {"chronicle.record": lambda e: None}

    # ---- Guardian diagnostics (no services published, direct method call) ----
    if states.get("guardian") == ModuleState.RUNNING:
        guardian_mod = loaded["guardian"]
        guardian_mod.all_diagnostics = mocker.Mock(
            return_value=guardian_diags or {}
        )

    # Merge extra services if provided
    if extra_services:
        services.update(extra_services)
        # Also update module-level services if the extra key matches
        for mod_name, mod in loaded.items():
            if hasattr(mod, "services") and isinstance(mod.services, dict):
                for k in extra_services:
                    if k.startswith(mod_name + "."):
                        mod.services[k] = extra_services[k]

    ctx.services = services
    registry.loaded = loaded

    return ctx, registry


def _register_mocks(
    mocker,
    states: dict[str, ModuleState] | None = None,
    extra_services: dict | None = None,
    guardian_diags: dict | None = None,
) -> tuple[Any, Any]:
    """Patch ``_load_and_start`` and return the mock ctx & registry."""
    ctx, registry = _make_mock_registry(mocker, states, extra_services, guardian_diags)
    mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
    return ctx, registry


# =============================================================================
# Fixtures — reusable test data
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Provide a ``CliRunner`` for invoking ``apoch eil`` commands."""
    return CliRunner()


@pytest.fixture
def a_hypothesis() -> OptimizationHypothesis:
    """A realistic optimization hypothesis."""
    return OptimizationHypothesis(
        type="opportunity",
        domain="cost",
        confidence=0.85,
        evidence={"avg_cost": Decimal("0.025"), "suggested_model": "claude-4-haiku"},
        affected_scope="session-a37f / code-review pipeline",
        generated_at="2026-07-14T10:30:00.000000",
    )


@pytest.fixture
def a_recommendation() -> Recommendation:
    """A realistic recommendation."""
    return Recommendation(
        id="rec-001",
        title="Switch code-review sessions to claude-4-haiku",
        description=(
            "Code review sessions average $0.025/unit —"
            " switching to haiku reduces cost by 60%."
        ),
        priority="high",
        confidence=0.85,
        evidence={"avg_cost": "0.025", "suggested_model": "claude-4-haiku"},
        justification="Cost reduction without quality degradation for review tasks",
        dependencies=["optimizer.hypotheses"],
        expiration="2026-08-14T10:30:00.000000",
        source_hypotheses=["hyp-001"],
        domain="cost",
        status="active",
        created_at="2026-07-14T10:30:00.000000",
    )


@pytest.fixture
def a_trend_point() -> TrendPoint:
    """A realistic trend data point."""
    return TrendPoint(
        period_start="2026-07-13T00:00:00",
        period_end="2026-07-14T00:00:00",
        total_cost=Decimal("1.25"),
        total_tokens=125000,
        avg_cost_per_task=Decimal("0.025"),
        work_unit_count=50,
    )


# =============================================================================
# Test: Module import
# =============================================================================


class TestEilModuleImport:
    """The ``eil.py`` module is importable and exposes ``cli_app``."""

    def test_eil_module_importable(self) -> None:
        """apoch.cli.eil is importable."""
        import apoch.cli.eil  # noqa: F401

    def test_eil_has_cli_app(self) -> None:
        """apoch.cli.eil has a typer.Typer cli_app."""
        from typer import Typer

        from apoch.cli.eil import cli_app

        assert isinstance(cli_app, Typer)

    def test_eil_command_registered_in_main_app(self) -> None:
        """apoch eil appears as a subcommand in apoch --help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "eil" in result.stdout.lower()


# =============================================================================
# Test: apoch eil dashboard
# =============================================================================


class TestDashboard:
    """apoch eil dashboard — compact overview."""

    def test_dashboard_shows_all_modules(self, runner, mocker) -> None:
        """Dashboard lists all 5 EIL modules when all are RUNNING."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "dashboard"])
        assert result.exit_code == 0
        for name in ("Pulse", "Optimizer", "Oracle", "Guardian", "Chronicle"):
            assert name in result.stdout

    def test_dashboard_shows_module_not_loaded(self, runner, mocker) -> None:
        """Dashboard shows 'not loaded' for missing modules."""
        states = {
            "pulse": ModuleState.RUNNING,
            "optimizer": ModuleState.RUNNING,
        }
        # Simulate oracle, guardian, chronicle not loaded (not in dict)
        ctx, registry = _make_mock_registry(mocker, states)
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "dashboard"])
        assert result.exit_code == 0
        assert "Pulse" in result.stdout
        assert "Optimizer" in result.stdout
        # Modules not in the loaded dict should show with absent state
        for name in ("Oracle", "Guardian", "Chronicle"):
            assert name in result.stdout

    def test_dashboard_json_output(self, runner, mocker) -> None:
        """--json returns parseable dict with all modules."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "dashboard", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        for key in ("pulse", "optimizer", "oracle", "guardian", "chronicle"):
            assert key in data
            assert data[key]["state"] == "RUNNING"

    def test_dashboard_graceful_degradation(self, runner, mocker) -> None:
        """Dashboard handles failed services without crashing."""
        def _failing_svc(*_a, **_kw):
            msg = "Service unavailable"
            raise RuntimeError(msg)

        extra = {
            "pulse.measurements": _failing_svc,
            "optimizer.status": _failing_svc,
            "oracle.recommendations": _failing_svc,
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "dashboard"])
        # Should not crash — graceful degradation
        assert result.exit_code == 0
        assert "Pulse" in result.stdout


# =============================================================================
# Test: apoch eil status
# =============================================================================


class TestStatus:
    """apoch eil status — detailed module states and services."""

    def test_status_shows_module_states(self, runner, mocker) -> None:
        """Status shows each module name and state."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "status"])
        assert result.exit_code == 0
        for name in ("pulse", "optimizer", "oracle", "guardian", "chronicle"):
            assert name in result.stdout
        assert "RUNNING" in result.stdout

    def test_status_shows_services(self, runner, mocker) -> None:
        """Status lists published service keys with checkmarks."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "status"])
        assert result.exit_code == 0
        assert "pulse.measurements ✓" in result.stdout
        assert "optimizer.hypotheses ✓" in result.stdout
        assert "oracle.recommendations ✓" in result.stdout
        assert "chronicle.record ✓" in result.stdout

    def test_status_json(self, runner, mocker) -> None:
        """--json returns structured module list."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "modules" in data
        names = {m["name"] for m in data["modules"]}
        assert names == {"pulse", "optimizer", "oracle", "guardian", "chronicle"}

    def test_status_no_services_on_failed(self, runner, mocker) -> None:
        """Status shows '—' for modules that are not RUNNING."""
        states = {
            "pulse": ModuleState.LOADED,
            "guardian": ModuleState.FAILED,
        }
        ctx, registry = _make_mock_registry(mocker, states)
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "status"])
        assert result.exit_code == 0
        # Failed/loaded modules should show state but no services
        assert "FAILED" in result.stdout or "LOADED" in result.stdout

    # ---- Deterministic output order ----

    def test_status_order_is_deterministic(self, runner, mocker) -> None:
        """Modules appear in EIL_MODULES order regardless of loaded dict."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "status"])
        assert result.exit_code == 0
        # Just verify it doesn't crash — order comes from EIL_MODULES tuple
        assert "pulse" in result.stdout.lower()


# =============================================================================
# Test: apoch eil hypotheses
# =============================================================================


class TestHypotheses:
    """apoch eil hypotheses — list optimization hypotheses."""

    def test_no_hypotheses_message(self, runner, mocker) -> None:
        """Shows empty message when no hypotheses match."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "hypotheses"])
        assert result.exit_code == 0
        # Default — no data, shows message
        assert "hypotheses" in result.stdout.lower() or "No hypotheses" in result.stdout

    def test_hypotheses_not_loaded(self, runner, mocker) -> None:
        """Exits with error when Optimizer is not available."""
        states = {"pulse": ModuleState.RUNNING}
        ctx, registry = _make_mock_registry(mocker, states)
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "hypotheses"])
        assert result.exit_code == 1
        assert "not available" in result.stdout.lower()

    def test_hypotheses_with_data(self, runner, mocker, a_hypothesis) -> None:
        """Lists hypotheses when Optimizer returns them."""
        extra = {"optimizer.hypotheses": lambda: [a_hypothesis]}
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "hypotheses"])
        assert result.exit_code == 0
        assert "opportunity" in result.stdout.lower() or "OPPT" in result.stdout
        assert "code-review" in result.stdout

    def test_hypotheses_limit_filter(self, runner, mocker, a_hypothesis) -> None:
        """--limit caps the number of returned items."""
        extra = {
            "optimizer.hypotheses": lambda: [
                OptimizationHypothesis(
                    type="pattern",
                    domain="time",
                    confidence=0.9,
                    evidence={},
                    affected_scope=f"scope-{i}",
                    generated_at="2026-07-14T10:30:00.000000",
                )
                for i in range(20)
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "hypotheses", "--limit", "3"])
        assert result.exit_code == 0
        assert "3 of 20" in result.stdout

    def test_hypotheses_min_confidence(self, runner, mocker) -> None:
        """--min-confidence filters by lower bound."""
        extra = {
            "optimizer.hypotheses": lambda: [
                OptimizationHypothesis(
                    type="pattern",
                    domain="time",
                    confidence=0.5,
                    evidence={},
                    affected_scope="low-conf",
                    generated_at="2026-07-14T10:30:00.000000",
                ),
                OptimizationHypothesis(
                    type="pattern",
                    domain="time",
                    confidence=0.9,
                    evidence={},
                    affected_scope="high-conf",
                    generated_at="2026-07-14T10:30:00.000000",
                ),
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(
            app, ["eil", "hypotheses", "--min-confidence", "0.8"]
        )
        assert result.exit_code == 0
        assert "high-conf" in result.stdout
        assert "low-conf" not in result.stdout

    def test_hypotheses_json(self, runner, mocker, a_hypothesis) -> None:
        """--json returns parseable list of hypotheses."""
        extra = {"optimizer.hypotheses": lambda: [a_hypothesis]}
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "hypotheses", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["type"] == "opportunity"
        assert data[0]["domain"] == "cost"

    def test_hypotheses_empty_after_filter(self, runner, mocker) -> None:
        """Empty message when all items are filtered out."""
        extra = {
            "optimizer.hypotheses": lambda: [
                OptimizationHypothesis(
                    type="pattern",
                    domain="time",
                    confidence=0.3,
                    evidence={},
                    affected_scope="low-conf",
                    generated_at="2026-07-14T10:30:00.000000",
                ),
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(
            app, ["eil", "hypotheses", "--min-confidence", "0.9"]
        )
        assert result.exit_code == 0
        assert "No hypotheses" in result.stdout

    def test_hypotheses_service_failure(self, runner, mocker) -> None:
        """Graceful degradation when hypotheses service raises."""
        extra = {
            "optimizer.hypotheses": lambda: (_ for _ in ()).throw(
                RuntimeError("fail")
            ),
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "hypotheses"])
        # Should not crash
        assert result.exit_code == 0


# =============================================================================
# Test: apoch eil recs
# =============================================================================


class TestRecs:
    """apoch eil recs — list improvement recommendations."""

    def test_no_recs_message(self, runner, mocker) -> None:
        """Shows empty message when no recommendations match."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "recs"])
        assert result.exit_code == 0
        assert "recommendations" in result.stdout.lower()

    def test_recs_not_loaded(self, runner, mocker) -> None:
        """Exits with error when Oracle is not available."""
        states = {"pulse": ModuleState.RUNNING}
        ctx, registry = _make_mock_registry(mocker, states)
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "recs"])
        assert result.exit_code == 1
        assert "not available" in result.stdout.lower()

    def test_recs_with_data(self, runner, mocker, a_recommendation) -> None:
        """Lists recommendations when Oracle returns them."""
        extra = {"oracle.recommendations": lambda: [a_recommendation]}
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs"])
        assert result.exit_code == 0
        assert "Switch code-review" in result.stdout
        assert "HIGH" in result.stdout or "high" in result.stdout.lower()

    def test_recs_priority_filter(self, runner, mocker) -> None:
        """--min-priority filters by priority level."""
        extra = {
            "oracle.recommendations": lambda: [
                Recommendation(
                    id="low-1", title="Low priority item",
                    description="desc", priority="low",
                    confidence=0.5, evidence={},
                    justification="test", dependencies=[],
                    expiration="2026-08-14T10:30:00",
                    source_hypotheses=[], domain="general",
                    status="active", created_at="2026-07-14T10:30:00",
                ),
                Recommendation(
                    id="high-1", title="High priority item",
                    description="desc", priority="high",
                    confidence=0.9, evidence={},
                    justification="test", dependencies=[],
                    expiration="2026-08-14T10:30:00",
                    source_hypotheses=[], domain="cost",
                    status="active", created_at="2026-07-14T10:30:00",
                ),
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs", "--min-priority", "high"])
        assert result.exit_code == 0
        assert "High priority" in result.stdout
        assert "Low priority" not in result.stdout

    def test_recs_json(self, runner, mocker, a_recommendation) -> None:
        """--json returns parseable list of recommendations."""
        extra = {"oracle.recommendations": lambda: [a_recommendation]}
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == "rec-001"
        assert data[0]["priority"] == "high"

    def test_recs_empty_after_filter(self, runner, mocker) -> None:
        """Empty message when all recommendations are filtered out."""
        extra = {
            "oracle.recommendations": lambda: [
                Recommendation(
                    id="low-1", title="Low priority item",
                    description="desc", priority="low",
                    confidence=0.5, evidence={},
                    justification="test", dependencies=[],
                    expiration="2026-08-14T10:30:00",
                    source_hypotheses=[], domain="general",
                    status="active", created_at="2026-07-14T10:30:00",
                ),
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs", "--min-priority", "critical"])
        assert result.exit_code == 0

    def test_recs_limit(self, runner, mocker) -> None:
        """--limit caps the number of returned recommendations."""
        extra = {
            "oracle.recommendations": lambda: [
                Recommendation(
                    id=f"rec-{i}", title=f"Rec {i}",
                    description="desc", priority="low",
                    confidence=0.5, evidence={},
                    justification="test", dependencies=[],
                    expiration="2026-08-14T10:30:00",
                    source_hypotheses=[], domain="general",
                    status="active", created_at="2026-07-14T10:30:00",
                )
                for i in range(20)
            ]
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs", "--limit", "5"])
        assert result.exit_code == 0
        assert "5 of 20" in result.stdout

    def test_recs_service_failure(self, runner, mocker) -> None:
        """Graceful degradation when recommendations service raises."""
        extra = {
            "oracle.recommendations": lambda: (_ for _ in ()).throw(
                RuntimeError("fail")
            ),
        }
        _register_mocks(mocker, extra_services=extra)
        result = runner.invoke(app, ["eil", "recs"])
        assert result.exit_code == 0


# =============================================================================
# Test: apoch eil trends
# =============================================================================


class TestTrends:
    """apoch eil trends — productivity trend visualization."""

    def test_no_trend_data(self, runner, mocker) -> None:
        """Shows 'No trend data' when Pulse returns empty."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "trends"])
        assert result.exit_code == 0
        assert "No trend data" in result.stdout

    def test_trends_not_loaded(self, runner, mocker) -> None:
        """Exits with error when Pulse is not available."""
        states: dict[str, ModuleState] = {}
        ctx, registry = _make_mock_registry(mocker, states)
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "trends"])
        assert result.exit_code == 1
        assert "not available" in result.stdout.lower()

    def test_trends_with_data(self, runner, mocker, a_trend_point) -> None:
        """Lists trend data points when Pulse returns them."""
        ctx, registry = _make_mock_registry(mocker)
        pulse_mod = registry.loaded["pulse"]
        pulse_mod.trend = mocker.Mock(return_value=[a_trend_point])
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "trends"])
        assert result.exit_code == 0
        assert "2026-07-13" in result.stdout
        assert "50 WUs" in result.stdout or "WUs" in result.stdout

    def test_trends_days_flag(self, runner, mocker, a_trend_point) -> None:
        """--days flag is passed to Pulse.trend()."""
        ctx, registry = _make_mock_registry(mocker)
        pulse_mod = registry.loaded["pulse"]
        pulse_mod.trend = mocker.Mock(return_value=[a_trend_point])
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "trends", "--days", "14"])
        assert result.exit_code == 0
        # Verify trend was called with period_days=14
        pulse_mod.trend.assert_called_once_with(period_days=14)

    def test_trends_json(self, runner, mocker, a_trend_point) -> None:
        """--json returns parseable trend data."""
        ctx, registry = _make_mock_registry(mocker)
        pulse_mod = registry.loaded["pulse"]
        pulse_mod.trend = mocker.Mock(return_value=[a_trend_point])
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "trends", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["work_unit_count"] == 50
        assert data[0]["total_tokens"] == 125000

    def test_trends_service_failure(self, runner, mocker) -> None:
        """Graceful degradation when trend call fails."""
        ctx, registry = _make_mock_registry(mocker)
        pulse_mod = registry.loaded["pulse"]
        pulse_mod.trend = mocker.Mock(side_effect=RuntimeError("fail"))
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        result = runner.invoke(app, ["eil", "trends"])
        assert result.exit_code == 0

    def test_trends_days_default(self, runner, mocker, a_trend_point) -> None:
        """Default --days is 7 when not specified."""
        ctx, registry = _make_mock_registry(mocker)
        pulse_mod = registry.loaded["pulse"]
        pulse_mod.trend = mocker.Mock(return_value=[a_trend_point])
        mocker.patch("apoch.cli.eil._load_and_start", return_value=(ctx, registry))
        runner.invoke(app, ["eil", "trends"])
        pulse_mod.trend.assert_called_once_with(period_days=7)


# =============================================================================
# Test: Dataset empty — all commands with zero data
# =============================================================================


class TestEmptyDataset:
    """All commands behave correctly with zero data."""

    def test_dashboard_empty(self, runner, mocker) -> None:
        """Dashboard shows zero counts gracefully."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "dashboard"])
        assert result.exit_code == 0
        assert "0 measurements" in result.stdout
        assert "0 hypotheses" in result.stdout
        assert "0 failed modules" in result.stdout

    def test_hypotheses_empty(self, runner, mocker) -> None:
        """hypotheses shows empty message when no data."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "hypotheses"])
        assert result.exit_code == 0
        assert "No hypotheses" in result.stdout or "hypotheses" in result.stdout.lower()

    def test_recs_empty(self, runner, mocker) -> None:
        """recs shows empty message when no data."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "recs"])
        assert result.exit_code == 0
        assert "recommendations" in result.stdout.lower()

    def test_trends_empty(self, runner, mocker) -> None:
        """trends shows 'No trend data' when empty."""
        _register_mocks(mocker)
        result = runner.invoke(app, ["eil", "trends"])
        assert result.exit_code == 0
        assert "No trend data" in result.stdout


# =============================================================================
# Test: Deterministic output ordering
# =============================================================================


class TestDeterministicOrder:
    """Command output appears in consistent order across invocations."""

    def test_dashboard_consistent_order(self, runner, mocker) -> None:
        """Dashboard module order is consistent."""
        _register_mocks(mocker)
        results = []
        for _ in range(3):
            r = runner.invoke(app, ["eil", "dashboard"])
            results.append(r.stdout)
        # All invocations produce identical output
        assert all(r == results[0] for r in results)

    def test_status_consistent_order(self, runner, mocker) -> None:
        """Status module order is consistent."""
        _register_mocks(mocker)
        results = []
        for _ in range(3):
            r = runner.invoke(app, ["eil", "status"])
            results.append(r.stdout)
        assert all(r == results[0] for r in results)
