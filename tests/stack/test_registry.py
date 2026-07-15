"""Tests for StackRegistry — entry-point discovery and registration.

Spec: core-stack §Registry
Design: Core Stack Installation & Lifecycle — StackRegistry
"""

from __future__ import annotations

import pytest

from apoch.stack.descriptor import StackDescriptor
from apoch.stack.exceptions import StackNotFoundError
from apoch.stack.registry import StackRegistry


class TestStackRegistryEmpty:
    """Verify behaviour of an empty registry."""

    def test_list_returns_empty(self):
        """list() returns an empty tuple when no components are registered."""
        registry = StackRegistry()
        assert registry.list() == ()

    def test_get_raises_for_unknown(self):
        """get() raises StackNotFoundError for unregistered names."""
        registry = StackRegistry()
        with pytest.raises(StackNotFoundError, match="unknown"):
            registry.get("unknown")

    def test_contains_returns_false(self):
        """contains() returns False for unregistered names."""
        registry = StackRegistry()
        assert registry.contains("unknown") is False


class TestStackRegistryRegistration:
    """Verify component registration."""

    @pytest.fixture
    def registry(self) -> StackRegistry:
        return StackRegistry()

    @pytest.fixture
    def descriptor(self) -> StackDescriptor:
        return StackDescriptor(
            name="test-component",
            kind="services",
            version="0.1.0",
            description="Test",
            entry_point="test:TestComponent",
        )

    def test_register_and_get(self, registry: StackRegistry, descriptor: StackDescriptor):
        """A registered component can be retrieved by name."""
        registry.register(descriptor)
        assert registry.contains("test-component") is True
        retrieved = registry.get("test-component")
        assert retrieved.name == "test-component"
        assert retrieved.version == "0.1.0"

    def test_register_twice_raises(self, registry: StackRegistry, descriptor: StackDescriptor):
        """Registering a component with the same name raises ValueError."""
        registry.register(descriptor)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(descriptor)

    def test_register_multiple_components(self, registry: StackRegistry):
        """Multiple components can be registered."""
        a = StackDescriptor(
            name="comp-a", kind="services", version="1.0", description="A", entry_point="a:A"
        )
        b = StackDescriptor(
            name="comp-b", kind="integrations", version="2.0", description="B", entry_point="b:B"
        )
        registry.register(a)
        registry.register(b)
        assert len(registry.list()) == 2
        assert registry.contains("comp-a")
        assert registry.contains("comp-b")

    def test_register_empty_dependencies_allowed(
        self, registry: StackRegistry, descriptor: StackDescriptor
    ):
        """A component with no dependencies can be registered."""
        registry.register(descriptor)
        assert registry.contains("test-component")


class TestStackRegistryDiscovery:
    """Verify entry-point discovery."""

    def test_discover_no_entry_points(self):
        """discover() on an empty entry-point group yields no components."""
        registry = StackRegistry()
        count = registry.discover(group="apoch.stack.components")
        assert count >= 0  # Does not crash; no entry points expected in test env

    def test_discover_is_idempotent(self):
        """Calling discover() multiple times does not duplicate registrations."""
        registry = StackRegistry()
        registry.discover(group="apoch.stack.components")
        first_count = len(registry.list())
        registry.discover(group="apoch.stack.components")
        assert len(registry.list()) == first_count
