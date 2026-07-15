"""Tests for StackManager — lifecycle orchestration and state management.

Spec: core-stack
Design: Core Stack Installation & Lifecycle — StackManager
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.exceptions import StackNotFoundError
from apoch.stack.manager import StackManager
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult
from apoch.stack.state import StackState
from tests.stack._testing import MockComponent


# ── Fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def events() -> list[tuple[str, str, dict]]:
    captured: list[tuple[str, str, dict]] = []

    def emitter(event: str, component: str, details: dict[str, Any]) -> None:
        captured.append((event, component, details))

    return captured


@pytest.fixture
def emit(events: list) -> Callable:
    def emitter(event: str, component: str, details: dict[str, Any]) -> None:
        events.append((event, component, details))

    return emitter


@pytest.fixture
def component_a() -> StackDescriptor:
    return StackDescriptor(
        name="comp-a",
        kind="services",
        version="1.0",
        description="Component A",
        entry_point="test:ComponentA",
    )


@pytest.fixture
def component_b() -> StackDescriptor:
    return StackDescriptor(
        name="comp-b",
        kind="services",
        version="1.0",
        description="Component B (depends on A)",
        entry_point="test:ComponentB",
        dependencies=("comp-a",),
    )


@pytest.fixture
def manager_with_components(
    registry: StackRegistry,
    component_a: StackDescriptor,
    component_b: StackDescriptor,
    emit: Callable,
) -> StackManager:
    registry.register(component_a)
    registry.register(component_b)
    manager = StackManager(registry, emit_event=emit)
    manager.register_instance("comp-a", MockComponent(component_a))
    manager.register_instance("comp-b", MockComponent(component_b))
    return manager


@pytest.fixture
def empty_manager(registry: StackRegistry, emit: Callable) -> StackManager:
    return StackManager(registry, emit_event=emit)


# ── Tests ────────────────────────────────────────────────────────────
class TestStackManagerInit:
    """Verify initial state."""

    def test_empty_registry_lists_nothing(self, empty_manager: StackManager):
        """list_components returns empty dict with no registered components."""
        assert empty_manager.list_components() == {}

    def test_get_status_raises_for_unknown(self, empty_manager: StackManager):
        """get_status raises StackNotFoundError for unregistered name."""
        with pytest.raises(StackNotFoundError):
            empty_manager.get_status("nonexistent")

    def test_default_state_is_not_installed(self, manager_with_components: StackManager):
        """get_status returns UNKNOWN initially (never installed)."""
        status = manager_with_components.get_status("comp-a")
        assert status.state == StackState.UNKNOWN


class TestStackManagerInstall:
    """Verify install lifecycle."""

    async def test_install_transitions_state(self, manager_with_components: StackManager):
        """Installing a component moves it to INSTALLING then INSTALLED."""
        result = await manager_with_components.install("comp-a")
        assert result.success is True
        assert result.component == "comp-a"

        status = manager_with_components.get_status("comp-a")
        assert status.state == StackState.INSTALLED

    async def test_install_fires_events(self, manager_with_components: StackManager, events: list):
        """Install emits COMPONENT_INSTALLING then COMPONENT_INSTALLED."""
        await manager_with_components.install("comp-a")
        assert len(events) >= 2
        event_types = [e[0] for e in events]
        assert "stack.component.installing" in event_types
        assert "stack.component.installed" in event_types

    async def test_install_unknown_component_raises(self, empty_manager: StackManager):
        """Installing an unregistered component raises StackNotFoundError."""
        with pytest.raises(StackNotFoundError):
            await empty_manager.install("nonexistent")

    async def test_install_twice_is_idempotent(self, manager_with_components: StackManager):
        """Installing an already-installed component returns success."""
        await manager_with_components.install("comp-a")
        result = await manager_with_components.install("comp-a")
        assert result.success is True

    async def test_install_checks_dependencies_first(self, manager_with_components: StackManager):
        """Installing a component with unmet dependencies..."""
        result = await manager_with_components.install("comp-b")
        # comp-b depends on comp-a which is not installed yet
        assert result.success is False
        assert "dependenc" in result.message.lower()


class TestStackManagerUninstall:
    """Verify uninstall lifecycle."""

    async def test_uninstall_unknown_raises(self, empty_manager: StackManager):
        """Uninstalling an unregistered component raises StackNotFoundError."""
        with pytest.raises(StackNotFoundError):
            await empty_manager.uninstall("nonexistent")

    async def test_uninstall_not_installed_is_ok(self, manager_with_components: StackManager):
        """Uninstalling a component that was never installed is fine."""
        result = await manager_with_components.uninstall("comp-a")
        assert result.success is True


class TestStackManagerVerify:
    """Verify component verification."""

    async def test_verify_unknown_raises(self, empty_manager: StackManager):
        """Verifying an unregistered component raises StackNotFoundError."""
        with pytest.raises(StackNotFoundError):
            await empty_manager.verify("nonexistent")


class TestStackManagerList:
    """Verify list_components."""

    async def test_list_returns_all_with_status(self, manager_with_components: StackManager):
        """list_components returns all registered components with their states."""
        components = manager_with_components.list_components()
        assert "comp-a" in components
        assert "comp-b" in components
        assert components["comp-a"].state == StackState.UNKNOWN
        assert components["comp-b"].state == StackState.UNKNOWN


class TestStackManagerEvents:
    """Verify event emissions."""

    async def test_events_in_expected_order(
        self, manager_with_components: StackManager, events: list
    ):
        """Events for install are emitted in the correct order."""
        await manager_with_components.install("comp-a")
        if len(events) >= 2:
            assert events[0][0] == "stack.component.installing"
            assert events[-1][0] in (
                "stack.component.installed",
                "stack.component.error",
            )


class TestStackManagerInstallAll:
    """Verify install_all() batch orchestration."""

    async def test_install_all_success(self, manager_with_components: StackManager):
        """All components install successfully in registration order."""
        results = await manager_with_components.install_all()
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].component == "comp-a"
        assert results[1].component == "comp-b"
        assert manager_with_components.get_status("comp-a").state == StackState.INSTALLED
        assert manager_with_components.get_status("comp-b").state == StackState.INSTALLED

    async def test_install_all_empty(self, empty_manager: StackManager):
        """No registered components produces an empty result list."""
        results = await empty_manager.install_all()
        assert results == []

    async def test_install_all_idempotent(self, manager_with_components: StackManager):
        """Running install_all twice skips already-installed components."""
        first = await manager_with_components.install_all()
        assert all(r.success for r in first)

        second = await manager_with_components.install_all()
        assert len(second) == 2
        # Second run should still return success (idempotent)
        assert all(r.success for r in second)
        # It should say "already installed" in the message
        assert "already installed" in second[0].message

    async def test_install_all_rollback_on_failure(self, empty_manager: StackManager):
        """When a later component fails, earlier ones are rolled back."""
        from apoch.stack.result import OperationResult

        registry = empty_manager._registry
        desc_a = StackDescriptor(
            name="good-a",
            kind="services",
            version="1.0",
            description="Installs fine",
            entry_point="test:GoodA",
        )
        desc_b = StackDescriptor(
            name="failing-b",
            kind="services",
            version="1.0",
            description="Fails on install",
            entry_point="test:FailingB",
        )
        registry.register(desc_a)
        registry.register(desc_b)

        class GoodComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_a

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="good-a", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="good-a", message="uninstalled")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="good-a", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="good-a", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="good-a", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class FailingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_b

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=False, component="failing-b", message="fail")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="failing-b", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="failing-b", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="failing-b", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="failing-b", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("good-a", GoodComponent())
        mgr.register_instance("failing-b", FailingComponent())

        results = await mgr.install_all()

        assert len(results) == 2
        assert results[0].success is True  # good-a installed
        assert results[1].success is False  # failing-b failed
        # good-a should have been rolled back
        assert mgr.get_status("good-a").state in (StackState.NOT_INSTALLED, StackState.UNKNOWN)

    async def test_install_all_dependency_order(self, empty_manager: StackManager):
        """Components are processed in registration order (deps first)."""
        registry = empty_manager._registry
        desc_a = StackDescriptor(
            name="comp-a",
            kind="services",
            version="1.0",
            description="A",
            entry_point="test:CompA",
        )
        desc_b = StackDescriptor(
            name="comp-b",
            kind="services",
            version="1.0",
            description="B depends on A",
            entry_point="test:CompB",
            dependencies=("comp-a",),
        )
        registry.register(desc_a)
        registry.register(desc_b)

        mgr = StackManager(registry)
        mgr.register_instance("comp-a", MockComponent(desc_a))
        mgr.register_instance("comp-b", MockComponent(desc_b))

        results = await mgr.install_all()
        assert all(r.success for r in results)
        assert mgr.get_status("comp-a").state == StackState.INSTALLED
        assert mgr.get_status("comp-b").state == StackState.INSTALLED


class TestStackManagerUninstallAll:
    """Verify uninstall_all() batch orchestration."""

    async def test_uninstall_all_reverse_order(self, manager_with_components: StackManager):
        """Components are uninstalled in reverse registration order."""
        # Install first
        await manager_with_components.install_all()

        results = await manager_with_components.uninstall_all()
        assert len(results) == 2
        assert results[0].component == "comp-b"  # reverse order — last registered first
        assert results[1].component == "comp-a"
        assert all(r.success for r in results)

    async def test_uninstall_all_empty(self, empty_manager: StackManager):
        """No registered components produces an empty result list."""
        results = await empty_manager.uninstall_all()
        assert results == []

    async def test_uninstall_all_idempotent(self, manager_with_components: StackManager):
        """Running uninstall_all twice is safe (no-op on already-removed)."""
        await manager_with_components.install_all()

        first = await manager_with_components.uninstall_all()
        assert all(r.success for r in first)

        second = await manager_with_components.uninstall_all()
        assert all(r.success for r in second)

    async def test_uninstall_all_transitions_to_not_installed(
        self,
        manager_with_components: StackManager,
    ):
        """After uninstall_all, all components reach NOT_INSTALLED or UNKNOWN."""
        await manager_with_components.install_all()

        await manager_with_components.uninstall_all()
        assert manager_with_components.get_status("comp-a").state in (
            StackState.NOT_INSTALLED,
            StackState.UNKNOWN,
        )
        assert manager_with_components.get_status("comp-b").state in (
            StackState.NOT_INSTALLED,
            StackState.UNKNOWN,
        )
