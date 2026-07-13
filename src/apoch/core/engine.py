"""Core Engine — bootstrap and lifecycle orchestrator.

Spec: module-system §Execution Flow
Design: Data Flow (Startup Flow, Shutdown Flow)

**Core dependency rule** (NON-NEGOTIABLE):
  ``apoch/core/`` may ONLY import:
    ✅ ``core/*`` (internal core modules)
    ✅ ``config/*`` (config package)
    ✅ Python stdlib

  It must NEVER import ``modules/*``, ``adapters/*``, ``stack/*``,
  ``cli/*``, or ``plugins/*``.
"""

from __future__ import annotations

import logging
from typing import Any

from apoch.core.events import EventBus
from apoch.core.module import Context
from apoch.core.registry import ModuleRegistry

logger = logging.getLogger(__name__)


class Engine:
    """Core bootstrap and lifecycle orchestrator.

    The Engine receives its dependencies at init time (constructor injection)
    and drives the module lifecycle in order:

        1. :meth:`start` — discover → load non-disabled → start all
        2. :meth:`stop` — stop all → shutdown all (reverse init order)

    **Orchestrator ONLY** — the Engine does NOT implement any module
    behaviour itself.  All module interaction goes through the
    :class:`Module` ABC interface.

    Usage::

        registry = ModuleRegistry(config)
        engine = Engine(registry=registry, config=config)
        await engine.start()
        # ... runtime ...
        await engine.stop()
    """

    def __init__(
        self,
        registry: ModuleRegistry,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._registry = registry
        self._config: dict[str, Any] = config or {}
        self._events = event_bus or EventBus()
        self._context: Context | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Bootstrap all non-disabled modules.

        1. Discover available modules.
        2. Load each module that is not explicitly disabled in config.
        3. Start all loaded modules.
        """
        logger.info("Engine starting...")

        discovered = self._registry.discover()
        logger.info("Discovered %d module(s)", len(discovered))

        # Load non-disabled modules.
        modules_config = self._config.get("modules", {})
        loaded_names: list[str] = []
        for meta in discovered:
            module_cfg = modules_config.get(meta.name, {})
            if module_cfg.get("enabled", True):
                self._registry.load(meta.name)
                loaded_names.append(meta.name)
                logger.info("Module '%s' loaded", meta.name)
            else:
                logger.info("Module '%s' is disabled — skipping", meta.name)

        # Start all loaded modules.
        self._context = Context()
        await self._registry.start_all(self._context)
        logger.info("Engine started — %d module(s) running", len(loaded_names))

        await self._events.emit("engine.started")

    async def stop(self) -> None:
        """Gracefully shut down all modules in reverse init order."""
        logger.info("Engine stopping...")
        await self._events.emit("engine.stopping")
        await self._registry.stop_all()
        self._context = None
        logger.info("Engine stopped")
        await self._events.emit("engine.stopped")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def registry(self) -> ModuleRegistry:
        """Return the module registry."""
        return self._registry

    @property
    def events(self) -> EventBus:
        """Return the event bus."""
        return self._events
