"""Tests for stack event type constants.

Design: Core Stack Installation & Lifecycle — Events-Only Observability
"""

from __future__ import annotations

from apoch.stack import events as ev


class TestEventConstants:
    """Verify event type constants exist and follow conventions."""

    def test_component_events_have_prefix(self):
        """All component events start with 'stack.component.'."""
        component_events = [
            ev.COMPONENT_INSTALLING,
            ev.COMPONENT_INSTALLED,
            ev.COMPONENT_UNINSTALLING,
            ev.COMPONENT_UNINSTALLED,
            ev.COMPONENT_ACTIVATING,
            ev.COMPONENT_ACTIVATED,
            ev.COMPONENT_DEACTIVATING,
            ev.COMPONENT_DEACTIVATED,
            ev.COMPONENT_VERIFYING,
            ev.COMPONENT_VERIFIED,
            ev.COMPONENT_ERROR,
            ev.COMPONENT_STATE_CHANGED,
        ]
        for event in component_events:
            assert event.startswith("stack.component."), f"{event} lacks stack.component. prefix"

    def test_lock_events_have_prefix(self):
        """All lock events start with 'stack.lock.'."""
        lock_events = [
            ev.STACK_LOCK_ACQUIRED,
            ev.STACK_LOCK_RELEASED,
            ev.STACK_LOCK_FAILED,
        ]
        for event in lock_events:
            assert event.startswith("stack.lock."), f"{event} lacks stack.lock. prefix"

    def test_all_events_are_strings(self):
        """All event constants are strings."""
        for name in dir(ev):
            if name.isupper() and not name.startswith("_"):
                val = getattr(ev, name)
                assert isinstance(val, str), f"{name} is not a string"
