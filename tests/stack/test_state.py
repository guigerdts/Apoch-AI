"""Tests for StackState enum and state machine.

Spec: core-stack
Design: Core Stack Installation & Lifecycle — State Model
"""

from __future__ import annotations

import pytest

from apoch.stack.component import ComponentInfo
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.state import StackState, derive_state


class TestStackStateValues:
    """Verify StackState has the correct 8 states."""

    def test_all_states_present(self):
        """StackState has the expected states."""
        assert len(StackState) == 11

    def test_unknown_state(self):
        """UNKNOWN is the default state."""
        assert StackState.UNKNOWN.value == "unknown"

    def test_not_installed_state(self):
        """NOT_INSTALLED indicates a component that has never been set up."""
        assert StackState.NOT_INSTALLED.value == "not_installed"

    def test_installing_state(self):
        """INSTALLING indicates active installation in progress."""
        assert StackState.INSTALLING.value == "installing"

    def test_installed_state(self):
        """INSTALLED indicates installed but not active."""
        assert StackState.INSTALLED.value == "installed"

    def test_active_state(self):
        """ACTIVE indicates installed and activated."""
        assert StackState.ACTIVE.value == "active"

    def test_inactive_state(self):
        """INACTIVE indicates deactivated but still installed."""
        assert StackState.INACTIVE.value == "inactive"

    def test_error_state(self):
        """ERROR indicates a failed installation."""
        assert StackState.ERROR.value == "error"

    def test_removed_state(self):
        """REMOVED indicates the component was uninstalled."""
        assert StackState.REMOVED.value == "removed"

    def test_outdated_state(self):
        """OUTDATED indicates version below minimum."""
        assert StackState.OUTDATED.value == "outdated"

    def test_unsupported_state(self):
        """UNSUPPORTED indicates version above maximum."""
        assert StackState.UNSUPPORTED.value == "unsupported"

    def test_broken_state(self):
        """BROKEN indicates verification failed."""
        assert StackState.BROKEN.value == "broken"


class TestStateTransitions:
    """Verify allowed transitions from each state."""

    @pytest.mark.parametrize(
        ("source", "target", "expected"),
        [
            (StackState.UNKNOWN, StackState.NOT_INSTALLED, True),
            (StackState.UNKNOWN, StackState.INSTALLED, False),
            (StackState.NOT_INSTALLED, StackState.INSTALLING, True),
            (StackState.NOT_INSTALLED, StackState.ACTIVE, False),
            (StackState.INSTALLING, StackState.INSTALLED, True),
            (StackState.INSTALLING, StackState.ERROR, True),
            (StackState.INSTALLING, StackState.ACTIVE, False),
            (StackState.INSTALLED, StackState.ACTIVE, True),
            (StackState.INSTALLED, StackState.ERROR, True),
            (StackState.INSTALLED, StackState.REMOVED, True),
            (StackState.INSTALLED, StackState.INSTALLING, False),
            (StackState.ACTIVE, StackState.INACTIVE, True),
            (StackState.ACTIVE, StackState.ERROR, True),
            (StackState.ACTIVE, StackState.INSTALLED, False),
            (StackState.INACTIVE, StackState.INSTALLED, True),
            (StackState.INACTIVE, StackState.ACTIVE, False),
            (StackState.ERROR, StackState.NOT_INSTALLED, True),
            (StackState.ERROR, StackState.INSTALLED, False),
            (StackState.REMOVED, StackState.UNKNOWN, True),
            (StackState.REMOVED, StackState.NOT_INSTALLED, False),
            (StackState.INSTALLED, StackState.OUTDATED, True),
            (StackState.INSTALLED, StackState.BROKEN, True),
            (StackState.OUTDATED, StackState.INSTALLED, True),
            (StackState.OUTDATED, StackState.ERROR, True),
            (StackState.OUTDATED, StackState.NOT_INSTALLED, False),
            (StackState.UNSUPPORTED, StackState.ERROR, True),
            (StackState.UNSUPPORTED, StackState.INSTALLED, False),
            (StackState.BROKEN, StackState.INSTALLED, True),
            (StackState.BROKEN, StackState.ERROR, True),
            (StackState.BROKEN, StackState.ACTIVE, False),
        ],
    )
    def test_transition(self, source: StackState, target: StackState, expected: bool):
        """can_transition_to returns expected result."""
        assert source.can_transition_to(target) is expected

    def test_identity_transitions_are_false(self):
        """A state cannot transition to itself."""
        for state in StackState:
            assert state.can_transition_to(state) is False


class TestStackStateStr:
    """Verify string representation."""

    def test_str_returns_value(self):
        """str(state) returns the state's value string."""
        assert str(StackState.INSTALLED) == "installed"
        assert str(StackState.ERROR) == "error"


class TestDeriveState:
    """Tests for the derive_state pure function."""

    def _make_descriptor(
        self,
        *,
        min_version: str = "",
        max_version: str = "",
    ) -> StackDescriptor:
        return StackDescriptor(
            name="test",
            kind="services",
            version="1.0.0",
            description="Test component",
            entry_point="test:test",
            min_version=min_version,
            max_version=max_version,
        )

    def test_derive_not_installed(self):
        """Not installed → NOT_INSTALLED."""
        desc = self._make_descriptor()
        info = ComponentInfo(installed=False)
        assert derive_state(desc, info) is StackState.NOT_INSTALLED

    def test_derive_no_version(self):
        """Installed with no version string → NOT_INSTALLED."""
        desc = self._make_descriptor()
        info = ComponentInfo(installed=True, version=None)
        assert derive_state(desc, info) is StackState.NOT_INSTALLED

    def test_derive_invalid_version(self):
        """Installed with unparseable version → NOT_INSTALLED."""
        desc = self._make_descriptor()
        info = ComponentInfo(installed=True, version="not-a-version")
        assert derive_state(desc, info) is StackState.NOT_INSTALLED

    def test_derive_installed(self):
        """Installed at a matching version → INSTALLED."""
        desc = self._make_descriptor()
        info = ComponentInfo(installed=True, version="1.0.0")
        assert derive_state(desc, info) is StackState.INSTALLED

    def test_derive_outdated(self):
        """Version below min_version → OUTDATED."""
        desc = self._make_descriptor(min_version="2.0.0")
        info = ComponentInfo(installed=True, version="1.5.0")
        assert derive_state(desc, info) is StackState.OUTDATED

    def test_derive_unsupported(self):
        """Version above max_version → UNSUPPORTED."""
        desc = self._make_descriptor(max_version="2.0.0")
        info = ComponentInfo(installed=True, version="3.0.0")
        assert derive_state(desc, info) is StackState.UNSUPPORTED

    def test_derive_min_version_boundary(self):
        """Version equal to min_version is INSTALLED (inclusive)."""
        desc = self._make_descriptor(min_version="2.0.0")
        info = ComponentInfo(installed=True, version="2.0.0")
        assert derive_state(desc, info) is StackState.INSTALLED

    def test_derive_max_version_boundary(self):
        """Version equal to max_version is INSTALLED (inclusive)."""
        desc = self._make_descriptor(max_version="2.0.0")
        info = ComponentInfo(installed=True, version="2.0.0")
        assert derive_state(desc, info) is StackState.INSTALLED

    def test_derive_outdated_takes_priority_over_unsupported(self):
        """When both min and max are set, min is evaluated first → OUTDATED wins."""
        desc = self._make_descriptor(min_version="3.0.0", max_version="1.0.0")
        info = ComponentInfo(installed=True, version="2.0.0")
        assert derive_state(desc, info) is StackState.OUTDATED
