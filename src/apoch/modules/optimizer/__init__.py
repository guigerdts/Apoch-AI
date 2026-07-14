"""Optimizer — Engineering Optimization Intelligence module."""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Lazy-import OptimizerModule to avoid circular/early import issues."""
    if name == "OptimizerModule":
        from apoch.modules.optimizer.module import OptimizerModule

        return OptimizerModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = ["OptimizerModule"]
