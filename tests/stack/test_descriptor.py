"""Tests for StackDescriptor dataclass.

Spec: core-stack §Descriptor
Design: Core Stack Installation & Lifecycle — StackComponent Interface
"""

from __future__ import annotations

import pytest

from apoch.stack.descriptor import StackDescriptor


class TestStackDescriptor:
    """Verify StackDescriptor creation and behaviour."""

    def test_minimal_descriptor(self):
        """A descriptor can be created with only required fields."""
        desc = StackDescriptor(
            name="engram",
            kind="services",
            version="1.0.0",
            description="Persistent memory service",
            entry_point="apoch.stack.components.engram:EngramComponent",
        )
        assert desc.name == "engram"
        assert desc.kind == "services"
        assert desc.version == "1.0.0"
        assert desc.description == "Persistent memory service"
        assert desc.entry_point == "apoch.stack.components.engram:EngramComponent"
        assert desc.dependencies == ()

    def test_descriptor_with_dependencies(self):
        """A descriptor can specify dependencies."""
        desc = StackDescriptor(
            name="oracle",
            kind="integrations",
            version="2.1.0",
            description="Oracle AI integration",
            entry_point="apoch.stack.components.oracle:OracleComponent",
            dependencies=("engram", "context7"),
        )
        assert desc.dependencies == ("engram", "context7")

    def test_descriptor_is_frozen(self):
        """StackDescriptor is frozen (immutable)."""
        desc = StackDescriptor(
            name="test",
            kind="services",
            version="0.1.0",
            description="Test",
            entry_point="test:Test",
        )
        with pytest.raises(AttributeError):
            desc.name = "changed"  # type: ignore[misc]

    def test_valid_kinds(self):
        """ComponentKind accepts only valid literals."""
        from typing import get_args

        from apoch.stack.descriptor import ComponentKind

        kinds = get_args(ComponentKind)
        assert "integrations" in kinds
        assert "store" in kinds
        assert "services" in kinds
        assert len(kinds) == 3

    def test_equality(self):
        """Two descriptors with the same fields are equal."""
        a = StackDescriptor(
            name="engram",
            kind="services",
            version="1.0.0",
            description="Persistent memory",
            entry_point="apoch.stack.components.engram:EngramComponent",
        )
        b = StackDescriptor(
            name="engram",
            kind="services",
            version="1.0.0",
            description="Persistent memory",
            entry_point="apoch.stack.components.engram:EngramComponent",
        )
        assert a == b
        assert hash(a) == hash(b)
