"""Tests for the Stack factory module."""

from __future__ import annotations

from apoch.stack.factory import create_manager
from apoch.stack.manager import StackManager


class TestCreateManager:
    """create_manager returns a properly wired StackManager."""

    def test_returns_stack_manager(self):
        mgr = create_manager()
        assert isinstance(mgr, StackManager)

    def test_discovers_openspec_component(self):
        mgr = create_manager()
        components = mgr.list_components()
        assert "OpenSpec" in components
        assert components["OpenSpec"].descriptor.id == "openspec"

    def test_is_fresh_instance(self):
        mgr1 = create_manager()
        mgr2 = create_manager()
        assert mgr1 is not mgr2
