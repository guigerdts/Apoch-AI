"""Tests for AgentAdapterManager.

Spec: agent-adapter §Module Tool Registration
Architecture: Manager bridges Registry + Adapter — no business logic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock


class _MockModule:
    """Module-like object with get_tool_defs for discovery testing."""

    def __init__(self, name: str, has_tools: bool = True) -> None:
        self.name = name
        self._has_tools = has_tools

    def get_tool_defs(self) -> list:
        if not self._has_tools:
            return []
        from apoch.adapters.base import ToolDef

        return [
            ToolDef(
                name=f"{self.name}_tool",
                description=f"Tool from {self.name}",
                input_schema={"type": "object"},
                handler_name="handle",
            ),
        ]

    def handle(self, **kwargs: Any) -> str:
        return f"{self.name}: {kwargs}"


def _mock_registry(modules: dict[str, Any]) -> Any:
    """Build a mock ModuleRegistry with the given loaded modules."""
    registry = MagicMock()
    type(registry).loaded = PropertyMock(return_value=modules)
    registry.discover.return_value = []
    registry.start_all = AsyncMock()
    registry.stop_all = AsyncMock()
    return registry


class TestAgentAdapterManager:
    """AgentAdapterManager orchestrates Engine + Adapter lifecycle."""

    def test_start_stops_idempotent(self) -> None:
        """start() and stop() can be called multiple times safely."""
        import asyncio

        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.stop = AsyncMock()
        adapter.health = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        registry = _mock_registry({})
        manager = AgentAdapterManager(adapter=adapter, registry=registry)

        async def _run() -> None:
            await manager.start()
            await manager.start()  # idempotent — should skip
            await manager.stop()
            await manager.stop()  # idempotent — should skip

        asyncio.run(_run())

        assert adapter.start.call_count == 1
        assert adapter.stop.call_count == 1

    def test_start_registers_tools_from_modules(self) -> None:
        """Manager registers coordinator then module tools."""
        import asyncio

        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.stop = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        mod_a = _MockModule("vision")
        mod_b = _MockModule("chronicle")
        registry = _mock_registry({"vision": mod_a, "chronicle": mod_b})
        manager = AgentAdapterManager(adapter=adapter, registry=registry)

        async def _run() -> None:
            await manager.start()
            await manager.stop()

        asyncio.run(_run())

        # Coordinator first (apoch_status), then 2 module tools in alpha order
        assert adapter.register_module_tools.call_count == 3
        call_args_list = adapter.register_module_tools.call_args_list
        assert call_args_list[0][0][0] == "coordinator"
        assert call_args_list[1][0][0] == "chronicle"
        assert call_args_list[2][0][0] == "vision"

    def test_start_without_tools_does_not_register(self) -> None:
        """Modules without get_tool_defs are skipped; coordinator still registers."""
        import asyncio

        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.stop = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        mod_no_tools = _MockModule("core", has_tools=False)
        registry = _mock_registry({"core": mod_no_tools})
        manager = AgentAdapterManager(adapter=adapter, registry=registry)

        async def _run() -> None:
            await manager.start()
            await manager.stop()

        asyncio.run(_run())

        # Coordinator registered (apoch_status), no module tools
        adapter.register_module_tools.assert_called_once()
        assert adapter.register_module_tools.call_args[0][0] == "coordinator"
