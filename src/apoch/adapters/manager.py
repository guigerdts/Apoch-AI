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
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

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
        self._coordinator: ApochCoordinator | None = None

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def coordinator(self) -> ApochCoordinator | None:
        """Return the ApochCoordinator, or None before :meth:`start`."""
        return self._coordinator

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

        # 3. Build ServiceRegistry and create Coordinator.
        # Read loaded modules from engine.registry (which may be mocked in tests).
        loaded = self._engine.registry.loaded
        services = ServiceRegistry(
            vision=loaded.get("vision"),
            chronicle=loaded.get("chronicle"),
            guardian=loaded.get("guardian"),
            pulse=loaded.get("pulse"),
            optimizer=loaded.get("optimizer"),
            oracle=loaded.get("oracle"),
        )
        self._coordinator = ApochCoordinator(services)
        logger.info("ApochCoordinator created with %d service(s)",
                     sum(1 for s in [services.vision, services.chronicle,
                                     services.guardian, services.pulse,
                                     services.optimizer, services.oracle]
                         if s is not None))

        # 4. Register coordinator tools (progressive registration).
        if self._coordinator is not None and hasattr(self._coordinator, "get_tool_defs"):
            coord_defs = self._coordinator.get_tool_defs()
            if coord_defs:
                await self._adapter.register_module_tools(
                    "coordinator", self._coordinator, coord_defs
                )

        # 4b. Register legacy aliases (PR9 — backward compatibility).
        if self._coordinator is not None and hasattr(self._coordinator, "get_legacy_aliases"):
            legacy_defs = self._coordinator.get_legacy_aliases()
            if legacy_defs:
                await self._adapter.register_module_tools(
                    "legacy", self._coordinator, legacy_defs
                )

        # 5. Discover and register existing module tool definitions.
        #    Deterministic: iterate sorted module names.
        module_tools: list[tuple[str, Any, list[ToolDef]]] = []
        for mod_name in sorted(loaded):
            mod = loaded[mod_name]
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

    async def serve(self) -> None:
        """Start and run the MCP gateway (blocking, stdio transport).

        Calls ``start()`` (which is idempotent and registers all
        module tools), then enters the stdio transport loop that
        blocks until cancelled.

        This is the main entry point for ``apoch mcp serve``.
        """
        await self.start()
        logger.info("AgentAdapterManager entering serve loop...")
        await self._adapter.serve()

        logger.info("AgentAdapterManager stopped")
