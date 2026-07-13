"""Adapter registry — maps agent names to adapter classes.

Architecture: This module provides a central registry for discovering
and resolving agent adapters by name.  In v1 only ``opencode`` is
registered; future PRs will add ``claude``, ``codex``, ``gemini``, etc.

Usage::

    from apoch.adapters.registry import get_adapter

    adapter_cls = get_adapter("opencode")
    adapter = adapter_cls(config={...})

Design: Registry is populated via entry points (``apoch.adapters``)
so third-party adapters can register without modifying Apoch-AI code.
"""

from __future__ import annotations

import logging
from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apoch.adapters.base import AgentAdapter

logger = logging.getLogger(__name__)

_registry: dict[str, type[AgentAdapter]] = {}


def register(name: str, adapter_cls: type[AgentAdapter]) -> None:
    """Register an adapter class under *name*."""
    _registry[name] = adapter_cls


def get_adapter(name: str, config: dict | None = None) -> AgentAdapter:
    """Return an instance of adapter *name* with the given *config*.

    Resolution order:
    1. Already-registered adapters (via ``register()``)
    2. Entry points (``apoch.adapters`` group)
    """
    cls = _registry.get(name)
    if cls is not None:
        return cls(config or {})

    return _resolve_entry_point(name, config or {})


def _resolve_entry_point(name: str, config: dict) -> AgentAdapter:
    """Resolve an adapter via ``apoch.adapters`` entry points."""
    try:
        eps = metadata.entry_points(group="apoch.adapters")
    except TypeError:
        eps = metadata.entry_points().get("apoch.adapters", [])

    for ep in eps:
        if ep.name == name:
            try:
                cls = ep.load()
                register(name, cls)
                return cls(config)
            except Exception as exc:
                logger.error("Failed to load adapter '%s': %s", name, exc)
                raise

    raise KeyError(f"No adapter registered for '{name}'")


def list_adapters() -> list[str]:
    """Return a list of all registered adapter names."""
    return list(_registry.keys())


# Register built-in adapters
from apoch.adapters.opencode.server import OpenCodeAdapter  # noqa: E402

register("opencode", OpenCodeAdapter)
