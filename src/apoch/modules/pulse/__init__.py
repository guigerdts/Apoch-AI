"""Pulse — engineering productivity intelligence for Apoch-AI.

Measures token consumption, cost, time, model efficiency, and rework
patterns across sessions, PRs, and features.  See
``openspec/changes/pulse-productivity-intelligence/`` for the full spec.
"""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Lazy-import sub-modules to avoid circular/early import issues."""
    import importlib

    if name == "PulseModule":
        module = importlib.import_module("apoch.modules.pulse.module")
        return module.PulseModule
    if name == "PulseStore":
        module = importlib.import_module("apoch.modules.pulse.storage")
        return module.PulseStore
    if name == "PulseEventSubscriber":
        module = importlib.import_module("apoch.modules.pulse.events")
        return module.PulseEventSubscriber
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = ["PulseModule", "PulseEventSubscriber", "PulseStore"]
