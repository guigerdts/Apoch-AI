"""Integration tests for the full Core Stack lifecycle.

Validates the complete flow end-to-end using fake components:
  install_all() → list_components() → uninstall_all()

All components are fakes — no real OpenSpec, Engram, Context7, or CodeGraph
are involved.  The StackManager orchestrates exclusively through the
``StackComponent`` interface.
"""

from __future__ import annotations

from apoch.stack.state import StackState
from tests.stack._testing import (
    _call_log,
    _reset_call_log,
    build_manager,
)

# ── Tests ────────────────────────────────────────────────────────────


class TestFullFlow:
    """install_all() → list_components() → uninstall_all() cycle."""

    async def test_initial_state(self):
        """Before any operation, all components start as UNKNOWN."""
        mgr = build_manager("comp-a", "comp-b", "comp-c")

        statuses = mgr.list_components()
        assert len(statuses) == 3
        for name, status in statuses.items():
            assert status.state is StackState.UNKNOWN, f"{name} should be UNKNOWN"

    async def test_install_all_transitions_states(self):
        """After install_all, all components reach INSTALLED."""
        mgr = build_manager("comp-a", "comp-b")
        _reset_call_log()

        results = await mgr.install_all()

        assert len(results) == 2
        assert all(r.success for r in results)

        statuses = mgr.list_components()
        assert statuses["comp-a"].state is StackState.INSTALLED
        assert statuses["comp-b"].state is StackState.INSTALLED

        # Verify call order
        assert _call_log == ["comp-a.install", "comp-b.install"]

    async def test_install_all_order(self):
        """Components install in registration order."""
        mgr = build_manager("comp-a", "comp-b", "comp-c")
        _reset_call_log()

        await mgr.install_all()

        assert _call_log == [
            "comp-a.install",
            "comp-b.install",
            "comp-c.install",
        ]

    async def test_install_all_idempotent(self):
        """Re-running install_all skips already-installed components."""
        mgr = build_manager("comp-a", "comp-b")
        _reset_call_log()

        await mgr.install_all()

        _reset_call_log()
        await mgr.install_all()

        # Behavioral: no actual install calls (idempotent)
        assert _call_log == []
        # State: components remain installed
        assert mgr.list_components()["comp-a"].state is StackState.INSTALLED
        assert mgr.list_components()["comp-b"].state is StackState.INSTALLED

    async def test_status_after_install(self):
        """list_components() returns correct states after install_all()."""
        mgr = build_manager("comp-a")
        _reset_call_log()

        await mgr.install_all()
        statuses = mgr.list_components()

        assert "comp-a" in statuses
        assert statuses["comp-a"].state is StackState.INSTALLED
        assert statuses["comp-a"].descriptor.name == "comp-a"

    async def test_uninstall_all_reverse_order(self):
        """uninstall_all() processes components in reverse registration order."""
        mgr = build_manager("comp-a", "comp-b", "comp-c")
        _reset_call_log()

        await mgr.install_all()
        _reset_call_log()

        await mgr.uninstall_all()

        assert _call_log == [
            "comp-c.uninstall",
            "comp-b.uninstall",
            "comp-a.uninstall",
        ]

    async def test_uninstall_all_returns_to_initial(self):
        """After uninstall_all, all components leave INSTALLED state."""
        mgr = build_manager("comp-a", "comp-b")
        _reset_call_log()

        await mgr.install_all()
        await mgr.uninstall_all()

        statuses = mgr.list_components()
        for name, status in statuses.items():
            assert status.state in (
                StackState.NOT_INSTALLED,
                StackState.REMOVED,
                StackState.UNKNOWN,
            ), f"{name} should no longer be installed, got {status.state}"

    async def test_full_cycle(self):
        """Full install → verify → uninstall → verify cycle completes cleanly."""
        mgr = build_manager("alpha", "beta", "gamma")
        _reset_call_log()

        # ── Install all ──────────────────────────────────────────────
        install_results = await mgr.install_all()
        assert len(install_results) == 3
        assert all(r.success for r in install_results)

        # Verify installed states
        statuses = mgr.list_components()
        assert statuses["alpha"].state is StackState.INSTALLED
        assert statuses["beta"].state is StackState.INSTALLED
        assert statuses["gamma"].state is StackState.INSTALLED

        # ── Uninstall all ────────────────────────────────────────────
        _reset_call_log()
        uninstall_results = await mgr.uninstall_all()
        assert len(uninstall_results) == 3
        assert all(r.success for r in uninstall_results)

        # Verify reverse order
        assert _call_log == [
            "gamma.uninstall",
            "beta.uninstall",
            "alpha.uninstall",
        ]

        # Verify final states
        statuses = mgr.list_components()
        for name in ("alpha", "beta", "gamma"):
            assert statuses[name].state not in (
                StackState.INSTALLED,
                StackState.ACTIVE,
            ), f"{name} should not be installed after uninstall"

    async def test_no_side_effects(self):
        """After the full cycle, no extra state leaks exist."""
        mgr = build_manager("comp-a")
        _reset_call_log()

        await mgr.install_all()

        # Capture state snapshot
        before = mgr.list_components()

        await mgr.uninstall_all()

        # Same keys, no new entries
        after = mgr.list_components()
        assert set(after.keys()) == {"comp-a"}
        assert set(before.keys()) == set(after.keys())

    async def test_install_uninstall_install_reinstall(self):
        """Clean re-install works after uninstall (no state contamination)."""
        mgr = build_manager("comp-a")
        _reset_call_log()

        # First cycle
        await mgr.install_all()
        assert mgr.list_components()["comp-a"].state is StackState.INSTALLED

        await mgr.uninstall_all()

        # Second cycle — should work identically
        _reset_call_log()
        await mgr.install_all()
        assert mgr.list_components()["comp-a"].state is StackState.INSTALLED
        assert _call_log == ["comp-a.install"]
