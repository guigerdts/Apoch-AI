"""Integration tests for ApochCoordinator.health() with REAL GuardianModule.

Uses the real GuardianModule to capture diagnostics via protect(),
backed by a minimal failing module.  Proves that health() reflects
REAL Guardian state — not just fake diagnostic dictionaries.

Design:
    - Real GuardianModule (from apoch.modules.guardian.module)
    - Real ApochCoordinator + ServiceRegistry
    - Fake modules only where necessary to trigger failures
    - Vision is a stub (the Guardian integration is what we test)
"""

from __future__ import annotations

import pytest

from apoch.core.module import Context, Module, ModuleState
from apoch.modules.guardian.module import GuardianModule
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _HealthyModule(Module):
    """Minimal module whose start() succeeds normally."""

    def __init__(self) -> None:
        super().__init__({})

    async def start(self, context: Context) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _FailingModule(Module):
    """Module whose start() raises RuntimeError — triggers Guardian.protect()."""

    def __init__(self, name: str = "_FailingModule") -> None:
        super().__init__({})
        self._module_name = name

    async def start(self, context: Context) -> None:
        msg = "simulated start failure"
        raise RuntimeError(msg)

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _FailingModuleAlpha(Module):
    """Separate class so Guardian._diagnostics has a distinct key."""

    def __init__(self) -> None:
        super().__init__({})

    async def start(self, context: Context) -> None:
        raise RuntimeError("alpha failure")

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _FailingModuleBeta(Module):
    """Separate class so Guardian._diagnostics has a distinct key."""

    def __init__(self) -> None:
        super().__init__({})

    async def start(self, context: Context) -> None:
        raise RuntimeError("beta failure")

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _VisionStub:
    """Minimal Vision stub that responds to module_state()."""

    async def module_state(self) -> dict:
        return {"state": "running", "modules": 0}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> Context:
    return Context()


# ---------------------------------------------------------------------------
# Tests — REAL GuardianModule integration
# ---------------------------------------------------------------------------


class TestHealthWithRealGuardian:
    """Verifies ApochCoordinator.health() against the real GuardianModule."""

    async def test_health_ok_when_no_failures(self, ctx: Context) -> None:
        """Guardian with empty diagnostics → healthy, non-degraded summary."""
        guardian = GuardianModule({})
        healthy = _HealthyModule()

        # Guard a successful start — no diagnostics captured
        result = await guardian.protect(healthy.start(ctx), healthy)
        assert result is None  # protect returns None on success
        assert len(guardian._diagnostics) == 0

        registry = ServiceRegistry()
        registry.guardian = guardian
        registry.vision = _VisionStub()

        coordinator = ApochCoordinator(registry)
        response = await coordinator.health()

        # health() returns ToolResponse dict — no "ok" field at this level
        assert response["healthy"] is True

        # Summary should not indicate any degradation
        assert "🟡" not in response["summary"]
        assert "🔴" not in response["summary"]

        # Suggested action indicates no action needed
        assert response["suggested_action"] == "Ninguna acción requerida"

        # Confidence is maximal when both Guardian and Vision respond
        assert response["confidence"] == 1.0

    async def test_health_failed_module_sets_unhealthy(self, ctx: Context) -> None:
        """Guardian.protect() catches a RuntimeError → healthy is False."""
        guardian = GuardianModule({})
        failing = _FailingModule()

        await guardian.protect(failing.start(ctx), failing)

        # --- Verify Guardian internals first ---
        diag = guardian._diagnostics.get("_FailingModule")
        assert diag is not None, "Guardian should have captured diagnostics"
        assert diag.current_state == ModuleState.FAILED.value
        assert "simulated start failure" in (diag.last_error or "")
        assert diag.fail_count == 1

        # --- Now test that health() reflects it ---
        registry = ServiceRegistry()
        registry.guardian = guardian
        registry.vision = _VisionStub()

        coordinator = ApochCoordinator(registry)
        response = await coordinator.health()

        assert response["healthy"] is False

        # Guardian must appear in evidence
        assert any(e["source"] == "Guardian" for e in response["evidence"])

        # The failing module must appear in the explanation
        assert "_FailingModule" in response["explanation"]

        # Summary reflects degradation (not the healthy default)
        assert response["summary"]
        assert "🟢" not in response["summary"]

        # suggested_action is different from the healthy no-op action
        assert response["suggested_action"]
        assert "_FailingModule" in response["suggested_action"]

        # Confidence is 1.0 because both sources responded
        assert response["confidence"] == 1.0

    async def test_health_multiple_failed_modules(self, ctx: Context) -> None:
        """Multiple failed modules → healthy is False, both in diagnostics."""
        guardian = GuardianModule({})

        failing_a = _FailingModuleAlpha()
        await guardian.protect(failing_a.start(ctx), failing_a)

        failing_b = _FailingModuleBeta()
        await guardian.protect(failing_b.start(ctx), failing_b)

        assert len(guardian._diagnostics) == 2
        assert all(
            d.current_state == ModuleState.FAILED.value for d in guardian._diagnostics.values()
        )

        registry = ServiceRegistry()
        registry.guardian = guardian
        registry.vision = _VisionStub()

        coordinator = ApochCoordinator(registry)
        response = await coordinator.health()

        assert response["healthy"] is False
        assert response["confidence"] == 1.0

        # Both failing module names appear in the explanation
        assert "_FailingModuleAlpha" in response["explanation"]
        assert "_FailingModuleBeta" in response["explanation"]

        # suggested_action references at least one of the failing modules
        assert response["suggested_action"]
        assert any(
            name in response["suggested_action"]
            for name in ("_FailingModuleAlpha", "_FailingModuleBeta")
        )

    async def test_health_without_guardian_dependency(self) -> None:
        """No Guardian in registry → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.vision = _VisionStub()
        # guardian is None by default

        coordinator = ApochCoordinator(registry)
        response = await coordinator.health()

        assert response["ok"] is False
        assert response["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_health_confidence_changes_with_available_sources(
        self,
        ctx: Context,
    ) -> None:
        """Confidence reflects n_available / n_expected (1/2 vs 2/2)."""
        guardian = GuardianModule({})

        # Test 1: Guardian only (no Vision) → confidence = 0.5
        registry_no_vision = ServiceRegistry()
        registry_no_vision.guardian = guardian

        coordinator_no_vision = ApochCoordinator(registry_no_vision)
        r_no_vision = await coordinator_no_vision.health()

        assert r_no_vision["confidence"] == 0.5

        # Test 2: Guardian + Vision → confidence = 1.0
        registry_full = ServiceRegistry()
        registry_full.guardian = GuardianModule({})
        registry_full.vision = _VisionStub()

        coordinator_full = ApochCoordinator(registry_full)
        r_full = await coordinator_full.health()

        assert r_full["confidence"] == 1.0

    async def test_health_is_idempotent(self) -> None:
        """Repeated calls return the same state."""
        registry = ServiceRegistry()
        registry.guardian = GuardianModule({})
        registry.vision = _VisionStub()

        coordinator = ApochCoordinator(registry)

        r1 = await coordinator.health()
        r2 = await coordinator.health()

        assert r1["healthy"] == r2["healthy"]
        assert r1["summary"] == r2["summary"]
        assert r1["confidence"] == r2["confidence"]
        assert r1["explanation"] == r2["explanation"]

    async def test_health_with_failure_is_idempotent(self, ctx: Context) -> None:
        """With a failed module, repeated calls return identical state."""
        guardian = GuardianModule({})
        failing = _FailingModule()
        await guardian.protect(failing.start(ctx), failing)

        registry = ServiceRegistry()
        registry.guardian = guardian
        registry.vision = _VisionStub()

        coordinator = ApochCoordinator(registry)

        r1 = await coordinator.health()
        r2 = await coordinator.health()

        assert r1["healthy"] is False
        # Both calls agree
        assert r1["healthy"] == r2["healthy"]
        assert r1["summary"] == r2["summary"]
        assert r1["confidence"] == r2["confidence"]
        assert r1["explanation"] == r2["explanation"]
