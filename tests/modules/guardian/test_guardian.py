"""Tests for GuardianModule — exception isolation and diagnostics.

Spec: module-guardian §Exception Isolation, §State Machine
Design: PR3B — Guardian Module §Testing Strategy
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.guardian.diagnostics import ModuleDiagnostics
from apoch.modules.guardian.module import GuardianModule

# =======================================================================
# Fixtures
# =======================================================================


@pytest.fixture
def guardian() -> GuardianModule:
    """Return a fresh GuardianModule in LOADED state."""
    return GuardianModule(config={})


@pytest.fixture
def context() -> Context:
    """Return a minimal execution context."""
    return Context()


class _HealthyModule(Module):
    """Minimal module that starts/stops cleanly."""

    async def start(self, context: Context) -> None:  # noqa: ARG002
        pass

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _BrokenModule(Module):
    """Module that raises during start()."""

    async def start(self, context: Context) -> None:  # noqa: ARG002
        msg = "invalid config"
        raise ValueError(msg)

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


@pytest.fixture
def healthy() -> _HealthyModule:
    return _HealthyModule(config={})


@pytest.fixture
def broken() -> _BrokenModule:
    return _BrokenModule(config={})


# =======================================================================
# Test: Diagnostics dataclass
# =======================================================================


class TestModuleDiagnostics:
    """ModuleDiagnostics dataclass structure and defaults."""

    def test_fields_are_accessible(self):
        """All six fields are readable."""
        diag = ModuleDiagnostics(
            module_name="TestModule",
            current_state="FAILED",
            last_error="ValueError: oops",
            last_error_traceback="Traceback (most recent call last):\n...",
            fail_count=3,
            last_failure_time="2026-07-13T12:00:00",
        )
        assert diag.module_name == "TestModule"
        assert diag.current_state == "FAILED"
        assert diag.last_error == "ValueError: oops"
        assert diag.last_error_traceback is not None
        assert diag.fail_count == 3
        assert diag.last_failure_time == "2026-07-13T12:00:00"

    def test_is_frozen(self):
        """ModuleDiagnostics is immutable."""
        diag = ModuleDiagnostics(
            module_name="X", current_state="LOADED", last_error=None,
            last_error_traceback=None, fail_count=0, last_failure_time=None,
        )
        with pytest.raises(AttributeError):
            diag.fail_count = 5  # type: ignore[misc]

    def test_nullable_fields_default_to_none(self):
        """last_error, last_error_traceback, last_failure_time may be None."""
        diag = ModuleDiagnostics(
            module_name="Clean", current_state="RUNNING",
            last_error=None, last_error_traceback=None,
            fail_count=0, last_failure_time=None,
        )
        assert diag.last_error is None
        assert diag.last_error_traceback is None
        assert diag.last_failure_time is None


# =======================================================================
# Test: Diagnostics retrieval API
# =======================================================================


class TestDiagnosticsAPI:
    """GuardianModule.diagnostics(), all_diagnostics(), clear_*."""

    def test_diagnostics_returns_none_for_unknown(self, guardian: GuardianModule):
        """Unknown modules return None."""
        assert guardian.diagnostics("GhostModule") is None

    def test_all_diagnostics_empty_initially(self, guardian: GuardianModule):
        """all_diagnostics() returns empty dict on fresh Guardian."""
        assert guardian.all_diagnostics() == {}

    def test_all_diagnostics_returns_copy(self, guardian: GuardianModule):
        """Returned dict is a copy — mutating it doesn't affect Guardian."""
        result = guardian.all_diagnostics()
        result["injected"] = None
        assert guardian.all_diagnostics() == {}

    def test_clear_diagnostics_removes_entry(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """After a failure, clear_diagnostics removes the entry."""
        # Induce a failure
        result = asyncio.run(guardian.protect(broken.start(context), broken))
        assert result is None
        assert guardian.diagnostics("_BrokenModule") is not None

        guardian.clear_diagnostics("_BrokenModule")
        assert guardian.diagnostics("_BrokenModule") is None

    def test_clear_all_diagnostics_clears_all(self, guardian: GuardianModule):
        """clear_all_diagnostics() empties the store."""
        # Manually inject a diagnostic to simulate known state
        guardian._diagnostics["M1"] = ModuleDiagnostics(
            module_name="M1", current_state="FAILED",
            last_error="err", last_error_traceback="tb",
            fail_count=1, last_failure_time="now",
        )
        guardian.clear_all_diagnostics()
        assert guardian.all_diagnostics() == {}

    def test_clear_nonexistent_is_noop(self, guardian: GuardianModule):
        """Clearing an unknown module does not raise."""
        guardian.clear_diagnostics("DoesNotExist")  # should not raise


# =======================================================================
# Test: protect() — success path
# =======================================================================


class TestProtectSuccess:
    """GuardianModule.protect() — happy path."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self, guardian: GuardianModule, healthy: _HealthyModule, context: Context):
        """protect() returns coroutine result on success."""
        result = await guardian.protect(healthy.start(context), healthy)
        assert result is None  # start() returns None

    @pytest.mark.asyncio
    async def test_returns_value_from_coro(self, guardian: GuardianModule):
        """protect() returns the actual coroutine return value."""

        async def return_forty_two() -> int:
            return 42

        result = await guardian.protect(return_forty_two(), _HealthyModule(config={}))
        assert result == 42

    @pytest.mark.asyncio
    async def test_module_state_stays_running(self, guardian: GuardianModule, healthy: _HealthyModule, context: Context):
        """After successful protect(), module state is RUNNING."""
        result = await guardian.protect(healthy.start(context), healthy)
        assert result is None  # protect() returns coroutine result
        assert healthy.state == ModuleState.RUNNING


# =======================================================================
# Test: protect() — failure path
# =======================================================================


class TestProtectFailure:
    """GuardianModule.protect() — exception handling."""

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """protect() returns None when the coroutine raises."""
        result = await guardian.protect(broken.start(context), broken)
        assert result is None

    @pytest.mark.asyncio
    async def test_sets_module_to_failed(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """On exception, module transitions to FAILED."""
        await guardian.protect(broken.start(context), broken)
        assert broken.state == ModuleState.FAILED

    @pytest.mark.asyncio
    async def test_captures_last_error(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """On exception, last_error captures type and message."""
        await guardian.protect(broken.start(context), broken)
        diag = guardian.diagnostics("_BrokenModule")
        assert diag is not None
        assert "ValueError" in (diag.last_error or "")
        assert "invalid config" in (diag.last_error or "")

    @pytest.mark.asyncio
    async def test_captures_traceback(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """On exception, last_error_traceback contains a real traceback."""
        await guardian.protect(broken.start(context), broken)
        diag = guardian.diagnostics("_BrokenModule")
        assert diag is not None
        assert diag.last_error_traceback is not None
        # The traceback mentions the file where start() raised
        assert "test_guardian.py" in diag.last_error_traceback
        assert "ValueError" in diag.last_error_traceback

    @pytest.mark.asyncio
    async def test_increments_fail_count(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """Each successive failure increments fail_count."""
        await guardian.protect(broken.start(context), broken)
        diag1 = guardian.diagnostics("_BrokenModule")
        assert diag1 is not None
        assert diag1.fail_count == 1

        await guardian.protect(broken.start(context), broken)
        diag2 = guardian.diagnostics("_BrokenModule")
        assert diag2 is not None
        assert diag2.fail_count == 2

    @pytest.mark.asyncio
    async def test_sets_failure_timestamp(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """last_failure_time is set to a valid ISO 8601 timestamp."""
        before = datetime.now(UTC)
        await guardian.protect(broken.start(context), broken)
        after = datetime.now(UTC)
        diag = guardian.diagnostics("_BrokenModule")
        assert diag is not None
        assert diag.last_failure_time is not None
        ts = datetime.fromisoformat(diag.last_failure_time)
        assert before <= ts <= after

    @pytest.mark.asyncio
    async def test_protect_does_not_catch_cancelled_error(self, guardian: GuardianModule, context: Context):
        """CancelledError propagates — Guardian never swallows cancellation."""

        async def cancelling_coro() -> None:
            raise asyncio.CancelledError()

        mod = _HealthyModule(config={})
        with pytest.raises(asyncio.CancelledError):
            await guardian.protect(cancelling_coro(), mod)

    @pytest.mark.asyncio
    async def test_protect_does_not_catch_keyboard_interrupt(self, guardian: GuardianModule, context: Context):
        """KeyboardInterrupt propagates — never swallowed."""

        async def interrupting_coro() -> None:
            raise KeyboardInterrupt()

        mod = _HealthyModule(config={})
        with pytest.raises(KeyboardInterrupt):
            await guardian.protect(interrupting_coro(), mod)


# =======================================================================
# Test: GuardianModule lifecycle
# =======================================================================


class TestGuardianLifecycle:
    """GuardianModule follows Module ABC lifecycle."""

    @pytest.mark.asyncio
    async def test_initial_state_is_loaded(self, guardian: GuardianModule):
        """GuardianModule starts in LOADED state."""
        assert guardian.state == ModuleState.LOADED

    @pytest.mark.asyncio
    async def test_start_transitions_to_running(self, guardian: GuardianModule, context: Context):
        """start() transitions LOADED → RUNNING."""
        await guardian.start(context)
        assert guardian.state == ModuleState.RUNNING

    @pytest.mark.asyncio
    async def test_stop_transitions_to_stopped(self, guardian: GuardianModule, context: Context):
        """stop() transitions RUNNING → STOPPED."""
        await guardian.start(context)
        await guardian.stop()
        assert guardian.state == ModuleState.STOPPED

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, guardian: GuardianModule, context: Context):
        """LOADED → RUNNING → STOPPED → SHUTDOWN."""
        await guardian.start(context)
        assert guardian.state == ModuleState.RUNNING
        await guardian.stop()
        assert guardian.state == ModuleState.STOPPED
        await guardian.shutdown()
        assert guardian.state == ModuleState.SHUTDOWN


# =======================================================================
# Test: stop() clears diagnostics
# =======================================================================


class TestStopClearsDiagnostics:
    """GuardianModule.stop() clears the in-memory diagnostics store."""

    @pytest.mark.asyncio
    async def test_stop_clears_diagnostics(self, guardian: GuardianModule, broken: _BrokenModule, context: Context):
        """After stop(), diagnostics dict is empty."""
        # Guardian must be RUNNING before we can stop()
        await guardian.start(context)
        await guardian.protect(broken.start(context), broken)
        assert len(guardian.all_diagnostics()) == 1
        await guardian.stop()
        assert guardian.all_diagnostics() == {}
