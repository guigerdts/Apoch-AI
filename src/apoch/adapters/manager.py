"""Agent Adapter Manager — orchestrates Engine + Adapter lifecycle.

Architecture: This module bridges the ModuleRegistry (core) and the
AgentAdapter (adapters).  It has no business logic — it only coordinates
the startup and shutdown sequence:

    1. Start the adapter (FastMCP gateway)
    2. Start the engine (load + start modules)
    3. Discover module tools and register with the adapter
    4. On stop: stop the adapter, stop the engine

Design constraint: The Manager does NOT import FastMCP or any concrete
adapter.  It receives the adapter instance via dependency injection.
"""

from __future__ import annotations

import logging
from typing import Any

from apoch.adapters.base import AgentAdapter, ToolDef
from apoch.core.engine import Engine
from apoch.core.exceptions import ApochError
from apoch.core.registry import ModuleRegistry

logger = logging.getLogger(__name__)


class AgentAdapterManager:
    """Orchestrates the Engine + Adapter lifecycle.

    Usage::

        adapter = get_adapter("opencode")
        registry = ModuleRegistry(config)
        manager = AgentAdapterManager(adapter=adapter, registry=registry)
        await manager.start()
        # ... runtime ...
        await manager.stop()
    """

    def __init__(
        self,
        adapter: AgentAdapter,
        registry: ModuleRegistry,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._adapter = adapter
        self._registry = registry
        self._config: dict[str, Any] = config or {}
        self._engine: Engine | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the gateway and register all module tools.

        Sequence:
          1. Start the adapter (FastMCP gateway).
          2. Create and start the Engine (module discovery + lifecycle).
          3. Discover tool definitions from every loaded module and
             register them with the adapter.

        Idempotent — subsequent calls are no-ops if already started.
        """
        if self._engine is not None:
            logger.warning("AgentAdapterManager already started — skipping")
            return

        logger.info("AgentAdapterManager starting...")

        # 1. Start adapter.
        await self._adapter.start()

        # 2. Start engine (loads and starts modules).
        self._engine = Engine(registry=self._registry, config=self._config)
        await self._engine.start()

        # 3. Discover and register tool definitions.
        #    Deterministic: iterate sorted module names.
        module_tools: list[tuple[str, Any, list[ToolDef]]] = []
        for mod_name in sorted(self._registry.loaded):
            mod = self._registry.loaded[mod_name]
            if hasattr(mod, "get_tool_defs"):
                defs = mod.get_tool_defs()
                if defs:
                    module_tools.append((mod_name, mod, defs))

        if module_tools:
            logger.info("Registering tools for %d module(s)...", len(module_tools))
            for mod_name, mod, defs in module_tools:
                try:
                    await self._adapter.register_module_tools(mod_name, mod, defs)
                except ApochError:
                    logger.exception(
                        "Failed to register tools for module '%s' — startup aborted",
                        mod_name,
                    )
                    raise

        logger.info("AgentAdapterManager started")

    async def stop(self) -> None:
        """Stop the gateway and engine.

        Idempotent — subsequent calls are no-ops.
        """
        if self._engine is None:
            return

        logger.info("AgentAdapterManager stopping...")
        await self._adapter.stop()
        await self._engine.stop()
        self._engine = None
        logger.info("AgentAdapterManager stopped")
