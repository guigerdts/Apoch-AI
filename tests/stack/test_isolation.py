"""Isolation, concurrency, and state consistency tests for StackManager.

Phase 13.2 — validates non-contractual properties of the Core Stack:
  - StackManager instances are fully independent (no global/mutable shared state).
  - State consistency through repeated install/uninstall cycles (no drift).
  - Concurrent operations on independent managers don't conflict.
  - Identically-named components in different managers are isolated.

All scenarios reuse the shared TrackerComponent fake from ``_testing.py``.
No production code is modified.
"""

from __future__ import annotations

import asyncio

from apoch.stack.state import StackState
from tests.stack._testing import build_manager


class TestManagerIsolation:
    """StackManager instances must not share mutable state.

    Each manager owns its own ``_statuses`` dict and component instances.
    Operations on one instance must never affect another.
    """

    async def test_managers_are_fully_independent(self):
        """Two managers with overlapping component names: install on one
        leaves the other's state unchanged.

        Property guaranteed: **Instance isolation** — ``StackManager``
        does not store state in any global/module-level data structure.
        """
        mgr_a = build_manager("comp-a", "comp-b")
        mgr_b = build_manager("comp-a", "comp-c")  # overlaps on "comp-a"

        await mgr_a.install_all()

        # mgr_a's comp-a is installed
        assert mgr_a.list_components()["comp-a"].state is StackState.INSTALLED

        # mgr_b's comp-a and comp-c are still UNKNOWN (untouched)
        assert mgr_b.list_components()["comp-a"].state is StackState.UNKNOWN
        assert mgr_b.list_components()["comp-c"].state is StackState.UNKNOWN

    async def test_same_components_no_crosstalk(self):
        """Two managers with *identical* component names are fully isolated.

        Property guaranteed: **Name isolation** — a component name is
        scoped to its manager.  No singleton registry or global component
        table leaks between instances.
        """
        mgr_a = build_manager("comp-a")
        mgr_b = build_manager("comp-a")

        await mgr_a.install_all()

        assert mgr_a.list_components()["comp-a"].state is StackState.INSTALLED
        assert mgr_b.list_components()["comp-a"].state is StackState.UNKNOWN


class TestStateConsistency:
    """Repeated lifecycle cycles must produce consistent state.

    The state machine must not drift over multiple install/uninstall
    rounds.  Every cycle starts and ends in the same states.
    """

    async def test_state_consistency_across_cycles(self):
        """Three consecutive install → uninstall cycles leave the manager
        in a consistent state after each step.

        Property guaranteed: **No state drift** — the install/uninstall
        code path is idempotent and does not accumulate latent state
        across cycles.
        """
        mgr = build_manager("comp-a")

        for cycle in range(3):
            # ── Install ─────────────────────────────────────────────────
            results = await mgr.install_all()
            assert all(r.success for r in results)
            assert mgr.list_components()["comp-a"].state is StackState.INSTALLED, (
                f"Cycle {cycle}: expected INSTALLED after install"
            )

            # ── Uninstall ───────────────────────────────────────────────
            results = await mgr.uninstall_all()
            assert all(r.success for r in results)
            current = mgr.list_components()["comp-a"].state
            assert current is StackState.NOT_INSTALLED, (
                f"Cycle {cycle}: expected NOT_INSTALLED after uninstall, got {current}"
            )


class TestConcurrencySafety:
    """Concurrent operations on independent managers must not interfere.

    Although StackManager is not designed for concurrent access to the
    *same* instance, operations on *different* instances must be safe
    under asyncio concurrency.
    """

    async def test_concurrent_independent_managers(self):
        """Run ``install_all()`` on three independent managers concurrently.

        Property guaranteed: **Async concurrency safety** — each manager
        owns its own event loop context (``_statuses``, ``_instances``).
        No cross-instance race conditions exist when the managers have
        disjoint or overlapping component names.
        """
        mgr_a = build_manager("alpha", "beta")
        mgr_b = build_manager("gamma", "delta")
        mgr_c = build_manager("epsilon", "zeta")

        results = await asyncio.gather(
            mgr_a.install_all(),
            mgr_b.install_all(),
            mgr_c.install_all(),
        )

        # All three batches succeeded
        assert len(results) == 3
        assert all(all(r.success for r in batch) for batch in results)

        # Each manager's components reached INSTALLED
        assert mgr_a.list_components()["alpha"].state is StackState.INSTALLED
        assert mgr_a.list_components()["beta"].state is StackState.INSTALLED
        assert mgr_b.list_components()["gamma"].state is StackState.INSTALLED
        assert mgr_b.list_components()["delta"].state is StackState.INSTALLED
        assert mgr_c.list_components()["epsilon"].state is StackState.INSTALLED
        assert mgr_c.list_components()["zeta"].state is StackState.INSTALLED
