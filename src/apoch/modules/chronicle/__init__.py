"""Chronicle — persistent activity recording for Apoch-AI.

Records lifecycle events, tool invocations, errors, and user actions
with a configurable retention period and SQLite-backed storage.
"""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Lazy-import sub-modules to avoid circular/early import issues."""
    import importlib

    if name == "ChronicleModule":
        module = importlib.import_module("apoch.modules.chronicle.module")
        return module.ChronicleModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = ["ChronicleModule"]
