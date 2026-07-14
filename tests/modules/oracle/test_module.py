"""Tests for OracleModule lifecycle and service wiring.

Spec: oracle-recommendation-engine §R1, R5, R6, R8, R9, R10, Constraint B
Design: Oracle — Recommendation Engine §Lifecycle, §Service Wiring, §Chronicle Integration
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from apoch.core.module import Context, ModuleState
from apoch.modules.optimizer.models import OptimizationHypothesis

if TYPE_CHECKING:
    pass  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_hyp(
    type_val: str = "pattern",
    domain: str = "cost",
    confidence: float = 0.85,
    evidence: dict | None = None,
    affected_scope: str = "all sessions",
    generated_at: str | None = None,
) -> OptimizationHypothesis:
    """Build an OptimizationHypothesis with defaults."""
    return OptimizationHypothesis(
        type=type_val,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        confidence=confidence,
        evidence=evidence or {"metric": "cpu", "value": 95},
        affected_scope=affected_scope,
        generated_at=generated_at or "2026-07-14T12:00:00",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> dict:
    """Default empty config for OracleModule."""
    return {"oracle": {}}


@pytest.fixture
def module(config):
    """Create an OracleModule in LOADED state (lazy import)."""
    from apoch.modules.oracle.module import OracleModule

    return OracleModule(config)


@pytest.fixture
def mock_hyp() -> OptimizationHypothesis:
    """Standard hypothesis fixture for cost/pattern."""
    return make_hyp()


# ===================================================================
# TestLifecycle — Module ABC state transitions
# ===================================================================


class TestLifecycle:
    """Module ABC lifecycle: LOADED → RUNNING → STOPPED → SHUTDOWN."""

    async def test_start_transitions_to_running(self, module) -> None:
        """start() should transition to RUNNING and instantiate engine."""
        context = Context(services={})
        await module.start(context)
        assert module.state == ModuleState.RUNNING
        assert module._engine is not None

    async def test_double_start_raises_error(self, module) -> None:
        """Calling start() twice MUST raise."""
        context = Context(services={})
        await module.start(context)
        with pytest.raises(Exception, match="state transition"):
            await module.start(context)

    async def test_stop_is_idempotent(self, module) -> None:
        """stop() should be safe to call multiple times."""
        context = Context(services={})
        await module.start(context)
        await module.stop()
        assert module.state == ModuleState.STOPPED
        # Second stop must NOT raise
        await module.stop()
        assert module.state == ModuleState.STOPPED

    async def test_shutdown_works(self, module) -> None:
        """shutdown() transitions STOPPED → SHUTDOWN."""
        context = Context(services={})
        await module.start(context)
        await module.stop()
        await module.shutdown()
        assert module.state == ModuleState.SHUTDOWN

    async def test_full_lifecycle(self, module) -> None:
        """Verify the complete lifecycle path."""
        context = Context(services={})
        assert module.state == ModuleState.LOADED
        await module.start(context)
        assert module.state == ModuleState.RUNNING
        await module.stop()
        assert module.state == ModuleState.STOPPED
        await module.shutdown()
        assert module.state == ModuleState.SHUTDOWN


# ===================================================================
# TestServiceWiring — services dict and callability
# ===================================================================


class TestServiceWiring:
    """OracleModule exposes oracle.recommendations and oracle.status."""

    async def test_services_dict_has_expected_keys(self, module) -> None:
        """Services dict MUST contain both expected keys."""
        assert "oracle.recommendations" in module.services
        assert "oracle.status" in module.services

    async def test_services_are_callable(self, module) -> None:
        """Each service entry MUST be callable."""
        assert callable(module.services["oracle.recommendations"])
        assert callable(module.services["oracle.status"])

    async def test_with_optimizer_returns_recommendations(
        self,
        module,
        mock_hyp,
    ) -> None:
        """With optimizer.hypotheses present, returns list[Recommendation]."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert len(recs) == 1
        # Verify it's a Recommendation instance
        from apoch.modules.oracle.models import Recommendation

        assert isinstance(recs[0], Recommendation)

    async def test_without_optimizer_returns_empty_list(self, module) -> None:
        """Without optimizer.hypotheses, returns []."""
        context = Context(services={})
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert recs == []


# ===================================================================
# TestOptimizerAbsent (R6)
# ===================================================================


class TestOptimizerAbsent:
    """Graceful degradation when Optimizer is absent."""

    async def test_no_optimizer_returns_empty(self, module) -> None:
        """No optimizer.hypotheses service → empty recommendations."""
        context = Context(services={})
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert recs == []

    async def test_no_optimizer_does_not_crash(self, module) -> None:
        """Must not crash when optimizer.hypotheses is absent."""
        context = Context(services={})
        await module.start(context)
        # Should not raise any exception
        _ = module.services["oracle.recommendations"]()


# ===================================================================
# TestChronicleAbsent (R5)
# ===================================================================


class TestChronicleAbsent:
    """Graceful degradation when Chronicle is absent (ephemeral mode)."""

    async def test_no_chronicle_still_returns_recs(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Without chronicle.record, recommendations are still returned."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert len(recs) == 1

    async def test_chronicle_absent_graceful_degradation(
        self,
        module,
        mock_hyp,
    ) -> None:
        """chronicle.record absent → no crash, recs returned."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert len(recs) == 1

    async def test_chronicle_raise_still_returns_recs(
        self,
        module,
        mock_hyp,
    ) -> None:
        """chronicle.record that raises → logged, recs still returned."""
        failing_record = MagicMock(side_effect=RuntimeError("chronicle down"))
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
            "chronicle.record": failing_record,
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert len(recs) == 1


# ===================================================================
# TestGuardianVisionAbsent (R7)
# ===================================================================


class TestGuardianVisionAbsent:
    """Graceful degradation when Guardian/Vision are absent."""

    async def test_no_guardian_no_vision_no_crash(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Without Guardian/Vision, recommendations still work."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        assert len(recs) == 1

    async def test_no_health_data_engine_uses_default_confidence(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Without Guardian/Vision, confidence is unmodified."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        recs = module.services["oracle.recommendations"]()
        # cost+pattern → base priority=high, base confidence=0.8
        assert recs[0].confidence == 0.8


# ===================================================================
# TestModuleDeterminism (R10)
# ===================================================================


class TestModuleDeterminism:
    """Same input × 2 → identical output."""

    async def test_same_input_identical_output(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Calling get_recommendations twice with same input must match."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)

        recs1 = module.services["oracle.recommendations"]()
        recs2 = module.services["oracle.recommendations"]()

        assert [asdict(r) for r in recs1] == [asdict(r) for r in recs2]

    async def test_determinism_with_chronicle(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Chronicle writes should not affect determinism of returned recs."""
        record_mock = MagicMock()
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
            "chronicle.record": record_mock,
        }
        context = Context(services=services)
        await module.start(context)

        recs1 = module.services["oracle.recommendations"]()
        recs2 = module.services["oracle.recommendations"]()

        assert [asdict(r) for r in recs1] == [asdict(r) for r in recs2]


# ===================================================================
# TestStatus — oracle.status shape and connectivity flags
# ===================================================================


class TestStatus:
    """oracle.status reflects service connectivity."""

    async def test_status_dict_has_correct_shape(self, module) -> None:
        """Status dict MUST have available, optimizer_connected, chronicle_connected."""
        context = Context(services={})
        await module.start(context)
        status = module.services["oracle.status"]()
        assert "available" in status
        assert "optimizer_connected" in status
        assert "chronicle_connected" in status
        assert status["available"] is True

    async def test_optimizer_connected_true_when_present(
        self,
        module,
        mock_hyp,
    ) -> None:
        """optimizer_connected is True when optimizer.hypotheses is present."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
        }
        context = Context(services=services)
        await module.start(context)
        status = module.services["oracle.status"]()
        assert status["optimizer_connected"] is True

    async def test_optimizer_connected_false_when_absent(self, module) -> None:
        """optimizer_connected is False when optimizer absent."""
        context = Context(services={})
        await module.start(context)
        status = module.services["oracle.status"]()
        assert status["optimizer_connected"] is False

    async def test_chronicle_connected_true_when_present(
        self,
        module,
        mock_hyp,
    ) -> None:
        """chronicle_connected is True when chronicle.record is present."""
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
            "chronicle.record": MagicMock(),
        }
        context = Context(services=services)
        await module.start(context)
        status = module.services["oracle.status"]()
        assert status["chronicle_connected"] is True

    async def test_chronicle_connected_false_when_absent(self, module) -> None:
        """chronicle_connected is False when chronicle absent."""
        context = Context(services={})
        await module.start(context)
        status = module.services["oracle.status"]()
        assert status["chronicle_connected"] is False


# ===================================================================
# TestChronicleWriting — event payload verification
# ===================================================================


class TestChronicleWriting:
    """Chronicle event writing via _try_record."""

    async def test_chronicle_writes_event_payload(
        self,
        module,
        mock_hyp,
    ) -> None:
        """Chronicle events contain full recommendation payload."""
        record_mock = MagicMock()
        services = {
            "optimizer.hypotheses": lambda: [mock_hyp],
            "chronicle.record": record_mock,
        }
        context = Context(services=services)
        await module.start(context)

        recs = module.services["oracle.recommendations"]()

        # Chronicle should have been called once per recommendation
        assert record_mock.call_count == len(recs)

        # Verify payload shape
        call_args = record_mock.call_args[0][0]
        assert call_args["type"] == "recommendation_generated"
        assert "payload" in call_args
        payload = call_args["payload"]
        assert payload["id"] == recs[0].id
        assert payload["title"] == recs[0].title
        assert payload["priority"] == recs[0].priority
        assert payload["domain"] == recs[0].domain

    async def test_chronicle_no_recs_no_write(self, module) -> None:
        """When recommendations is empty, Chronicle should NOT be called."""
        record_mock = MagicMock()
        services = {
            "optimizer.hypotheses": lambda: [],
            "chronicle.record": record_mock,
        }
        context = Context(services=services)
        await module.start(context)

        _ = module.services["oracle.recommendations"]()
        record_mock.assert_not_called()

    async def test_chronicle_absent_no_write_attempt(self, module) -> None:
        """When chronicle.record is absent, no write attempt errors."""
        services: dict = {
            "optimizer.hypotheses": lambda: [],
        }
        context = Context(services=services)
        await module.start(context)
        # Should not raise
        _ = module.services["oracle.recommendations"]()


# ===================================================================
# TestLazyImport — __init__.py lazy loading
# ===================================================================


class TestLazyImport:
    """Package __init__.py lazy-imports OracleModule."""

    def test_lazy_import_resolves(self) -> None:
        """OracleModule should be accessible via lazy import."""
        import sys

        # Ensure the module is not cached
        for modname in list(sys.modules):
            if "apoch.modules.oracle" in modname:
                del sys.modules[modname]

        from apoch.modules.oracle import OracleModule  # type: ignore[attr-defined]

        assert callable(OracleModule)

    def test_lazy_import_not_loaded_at_init(self) -> None:
        """OracleModule should NOT be imported at package init time."""
        import sys

        for modname in list(sys.modules):
            if "apoch.modules.oracle" in modname:
                del sys.modules[modname]

        # Import the package (not the module)
        import importlib as _il

        import apoch.modules.oracle  # noqa: F811

        _il.reload(apoch.modules.oracle)

        # The module.py should NOT be import-loaded yet
        assert "apoch.modules.oracle.module" not in sys.modules
