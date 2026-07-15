"""Factory functions for constructing wired Stack dependencies.

Design: Core Stack Installation & Lifecycle — Dependency Injection
This module is the single place where Stack components are assembled.
No other module constructs ``StackRegistry`` or ``StackManager`` directly.
"""

from __future__ import annotations

from apoch.stack.manager import StackManager
from apoch.stack.registry import StackRegistry


def create_manager() -> StackManager:
    """Create a fully wired :class:`StackManager`.

    Discovers registered components via ``importlib.metadata`` entry
    points (``apoch.stack.components`` group) and returns a manager
    ready for lifecycle operations.

    Usage::

        from apoch.stack import create_manager

        manager = create_manager()
        results = await manager.install_all()

    Returns:
        A :class:`StackManager` with entry-point discovery already
        loaded.  Safe to call repeatedly — each call returns a fresh
        manager (no global state).
    """
    registry = StackRegistry()
    registry.discover()
    return StackManager(registry)
