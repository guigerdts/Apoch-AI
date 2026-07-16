"""Tests for AgentAdapterManager wiring with ApochCoordinator.

Design: ADR-001 (ServiceRegistry injection), ADR-006 (backward compat)
Spec: mcp-public-api §Architecture Review

Verifies that the Manager:
1. Builds ServiceRegistry from engine modules
2. Creates ApochCoordinator with correct services
3. Registers existing module tools (unchanged)
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from apoch.adapters.base import ToolDef
from apoch.core.registry import ModuleRegistry


class TestManagerWiring:
    """AgentAdapterManager builds ServiceRegistry and creates Coordinator."""

    async def test_manager_builds_service_registry(self, mocker):
        """Manager creates ServiceRegistry from engine's loaded modules."""
        from apoch.adapters.manager import AgentAdapterManager

        # Mock adapter
        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.stop = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        # Mock engine registry loaded modules
        mock_vision = MagicMock()
        mock_chronicle = MagicMock()
        mock_guardian = MagicMock()

        mock_engine = MagicMock()
        type(mock_engine).registry = PropertyMock(
            return_value=MagicMock(
                loaded={
                    "vision": mock_vision,
                    "chronicle": mock_chronicle,
                    "guardian": mock_guardian,
                }
            )
        )
        mock_engine.start = AsyncMock()
        mock_engine.stop = AsyncMock()

        # Patch Engine constructor
        mocker.patch("apoch.adapters.manager.Engine", return_value=mock_engine)

        real_registry = ModuleRegistry()
        manager = AgentAdapterManager(adapter=adapter, registry=real_registry)

        await manager.start()

        # Verify coordinator was created
        assert manager.coordinator is not None
        # Verify services were mapped correctly
        assert manager.coordinator._services.vision is mock_vision
        assert manager.coordinator._services.chronicle is mock_chronicle
        assert manager.coordinator._services.guardian is mock_guardian
        # Verify unloaded services are None
        assert manager.coordinator._services.pulse is None
        assert manager.coordinator._services.optimizer is None
        assert manager.coordinator._services.oracle is None

    async def test_manager_empty_registry(self, mocker):
        """Manager handles empty registry (no modules loaded)."""
        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        mock_engine = MagicMock()
        type(mock_engine).registry = PropertyMock(return_value=MagicMock(loaded={}))
        mock_engine.start = AsyncMock()
        mock_engine.stop = AsyncMock()

        mocker.patch("apoch.adapters.manager.Engine", return_value=mock_engine)

        manager = AgentAdapterManager(adapter=adapter, registry=ModuleRegistry())
        await manager.start()

        assert manager.coordinator is not None
        assert manager.coordinator._services.vision is None
        assert manager.coordinator._services.chronicle is None
        assert manager.coordinator._services.guardian is None

    async def test_manager_still_registers_module_tools(self, mocker):
        """Existing module tool registration still happens unchanged."""
        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()
        adapter.register_module_tools = AsyncMock()

        mock_module = MagicMock()
        mock_module.get_tool_defs.return_value = [
            ToolDef(
                name="test_tool",
                description="A test tool",
                input_schema={"type": "object", "properties": {}},
                handler_name="handle_test",
            ),
        ]

        # Create real ModuleRegistry with a loaded module
        real_registry = ModuleRegistry()
        real_registry._loaded = {"test_mod": mock_module}
        real_registry._init_order = ["test_mod"]

        mock_engine = MagicMock()
        type(mock_engine).registry = PropertyMock(
            return_value=MagicMock(loaded={"test_mod": mock_module})
        )
        mock_engine.start = AsyncMock()

        mocker.patch("apoch.adapters.manager.Engine", return_value=mock_engine)

        manager = AgentAdapterManager(adapter=adapter, registry=real_registry)
        await manager.start()

        # Verify module tools were registered
        adapter.register_module_tools.assert_any_call(
            "test_mod", mock_module, mock_module.get_tool_defs.return_value
        )

    async def test_coordinator_accessible_after_start(self, mocker):
        """Coordinator property returns None before start, instance after."""
        from apoch.adapters.manager import AgentAdapterManager

        adapter = AsyncMock()
        adapter.start = AsyncMock()

        mock_engine = MagicMock()
        type(mock_engine).registry = PropertyMock(return_value=MagicMock(loaded={}))
        mock_engine.start = AsyncMock()
        mock_engine.stop = AsyncMock()

        mocker.patch("apoch.adapters.manager.Engine", return_value=mock_engine)

        manager = AgentAdapterManager(adapter=adapter, registry=ModuleRegistry())

        # Before start, coordinator is None
        assert manager.coordinator is None

        await manager.start()

        # After start, coordinator is created
        assert manager.coordinator is not None

        await manager.stop()

        # After stop... actually stop doesn't clear the coordinator
        # The engine is cleared but coordinator stays accessible
