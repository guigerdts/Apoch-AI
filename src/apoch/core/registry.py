"""Module Registry — discovers, loads, and manages module lifecycle.

Spec: module-system §Entry Point Discovery, §Enable/Disable
Design: Data Flow (Startup Flow)
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Any

from apoch.core.exceptions import ModuleLoadError
from apoch.core.module import Context, Module, ModuleMetadata, ModuleState

logger = logging.getLogger(__name__)

# Sentinel type for the Guardian reference — we duck-type instead of
# importing from ``modules.guardian`` to keep Core import-free.
_GuardianLike = Any


class ModuleRegistry:
    """Discovers and loads Apoch-AI modules, drives lifecycle.

    **Registrar/discoverer ONLY** — no business logic.  Discovers modules,
    loads on demand, and filters by config.  Never auto-instantiates during
    discovery.

    When a module named ``guardian`` is loaded, the registry stores an
    internal reference and delegates lifecycle calls to
    ``GuardianModule.protect()`` for all *other* modules.  Guardian's own
    lifecycle uses a raw try/except (it cannot protect itself).

    Usage::

        reg = ModuleRegistry(config)
        metadata = reg.discover()
        mod = reg.load("chronicle")
        await reg.start_all(context)
        await reg.stop_all()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = config or {}
        self._loaded: dict[str, Module] = {}
        self._init_order: list[str] = []
        self._guardian: _GuardianLike = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[ModuleMetadata]:
        """Discover all modules registered under the ``apoch.modules`` entry point group.

        Returns metadata only — never instantiates modules.  Call
        :meth:`load` separately to create a :class:`Module` instance.
        """
        result: list[ModuleMetadata] = []
        for ep in entry_points(group="apoch.modules"):
            meta = ModuleMetadata(
                name=ep.name,
                version=_version_from_ep(ep) or "0.0.0",
                description=_description_from_ep(ep) or "",
                entry_point=ep.value,
            )
            result.append(meta)
        return result

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def load(self, name: str) -> Module:
        """Load and return a :class:`Module` instance by *name*.

        Raises :exc:`ModuleLoadError` if the entry point is not found or
        cannot be loaded.  Subsequent calls return the cached instance.
        """
        if name in self._loaded:
            return self._loaded[name]

        # Find entry point by name
        eps = entry_points(group="apoch.modules")
        target = None
        for ep in eps:
            if ep.name == name:
                target = ep
                break

        if target is None:
            raise ModuleLoadError(f"Module '{name}' not found in apoch.modules entry points")

        # Load the entry point class
        try:
            module_class = target.load()
        except Exception as exc:
            raise ModuleLoadError(f"Failed to load entry point for module '{name}': {exc}") from exc

        # Build module-specific config
        modules_config = self._config.get("modules", {})
        module_config: dict[str, Any] = modules_config.get(name, {})

        try:
            instance: Module = module_class(config=module_config)
        except Exception as exc:
            raise ModuleLoadError(f"Failed to instantiate module '{name}': {exc}") from exc

        self._loaded[name] = instance
        self._init_order.append(name)

        # Capture Guardian reference — Core must NOT import modules.guardian
        if name == "guardian":
            self._guardian = instance

        return instance

    # ------------------------------------------------------------------
    # Lifecycle orchestration
    # ------------------------------------------------------------------

    async def start_all(self, context: Context) -> None:
        """Call ``start(context)`` on each loaded module in init order.

        If the ``guardian`` module is loaded, its ``protect()`` method
        wraps each non-Guardian lifecycle call with exception isolation.
        Guardian's own lifecycle uses a raw try/except (self-protection
        is impossible).
        """
        for name in self._init_order:
            mod = self._loaded[name]
            use_guardian = (
                self._guardian is not None
                and mod is not self._guardian
                and hasattr(self._guardian, "protect")
            )
            if use_guardian:
                await self._guardian.protect(mod.start(context), mod)
            else:
                # Raw try/except for Guardian itself, or if no Guardian
                # is loaded (backward-compatible fallback).
                try:
                    await mod.start(context)
                except Exception as exc:
                    logger.exception("Module '%s' failed during start(): %s", name, exc)
                    mod._state = ModuleState.FAILED  # type: ignore[attr-defined]

    async def stop_all(self) -> None:
        """Call ``stop()`` then ``shutdown()`` in reverse init order.

        Uses the same Guardian delegation pattern as :meth:`start_all`.
        """
        for name in reversed(self._init_order):
            mod = self._loaded[name]
            use_guardian = (
                self._guardian is not None
                and mod is not self._guardian
                and hasattr(self._guardian, "protect")
            )
            if use_guardian:
                await self._guardian.protect(mod.stop(), mod)
            else:
                try:
                    await mod.stop()
                except Exception as exc:
                    logger.exception("Module '%s' failed during stop(): %s", name, exc)
            if use_guardian:
                await self._guardian.protect(mod.shutdown(), mod)
            else:
                try:
                    await mod.shutdown()
                except Exception as exc:
                    logger.exception("Module '%s' failed during shutdown(): %s", name, exc)

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def loaded(self) -> dict[str, Module]:
        """Return a read-only view of loaded modules (copy)."""
        return dict(self._loaded)

    @property
    def init_order(self) -> list[str]:
        """Return a copy of the module init order."""
        return list(self._init_order)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _version_from_ep(ep) -> str | None:
    """Get the distribution version from an entry point, if available."""
    if ep.dist is not None:
        return str(ep.dist.version)
    return None


def _description_from_ep(ep) -> str | None:
    """Get the distribution summary from an entry point, if available."""
    if ep.dist is not None:
        return ep.dist.metadata.get("Summary", None)
    return None
