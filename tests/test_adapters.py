"""Tests for AgentAdapter ABC (RED phase).

Spec: agent-adapter §Adapter ABC Contract
Architecture: Core MUST NOT depend on any concrete adapter.
Design: AgentAdapter ABC with start, stop, health, register_module_tools.

RED-GREEN phases:
  RED:   Tests 1–N MUST fail — adapters package does not exist yet.
  GREEN: After creating adapters/base.py, all tests MUST pass.
"""

from __future__ import annotations

import pytest


class TestHealthStatus:
    """HealthStatus dataclass — returned by adapter.health()."""

    def test_health_status_importable(self) -> None:
        """RED: HealthStatus is importable from apoch.adapters.base."""
        from apoch.adapters.base import HealthStatus  # noqa: F401

    def test_health_status_is_dataclass(self) -> None:
        """HealthStatus is a dataclass."""
        from dataclasses import is_dataclass

        from apoch.adapters.base import HealthStatus

        assert is_dataclass(HealthStatus)

    def test_health_status_fields(self) -> None:
        """HealthStatus has healthy, uptime_seconds, error fields."""
        from apoch.adapters.base import HealthStatus

        h = HealthStatus(healthy=True, uptime_seconds=42.0, error=None)
        assert h.healthy is True
        assert h.uptime_seconds == 42.0
        assert h.error is None

    def test_health_status_error_optional(self) -> None:
        """HealthStatus.error defaults to None."""
        from apoch.adapters.base import HealthStatus

        h = HealthStatus(healthy=False)
        assert h.healthy is False
        assert h.uptime_seconds is None
        assert h.error is None


class TestToolDef:
    """ToolDef dataclass — module tool descriptor."""

    def test_tool_def_importable(self) -> None:
        """RED: ToolDef is importable from apoch.adapters.base."""
        from apoch.adapters.base import ToolDef  # noqa: F401

    def test_tool_def_is_dataclass(self) -> None:
        """ToolDef is a dataclass."""
        from dataclasses import is_dataclass

        from apoch.adapters.base import ToolDef

        assert is_dataclass(ToolDef)

    def test_tool_def_fields(self) -> None:
        """ToolDef has name, description, input_schema, handler_name fields."""
        from apoch.adapters.base import ToolDef

        t = ToolDef(
            name="list",
            description="List items",
            input_schema={"type": "object"},
            handler_name="list_items",
        )
        assert t.name == "list"
        assert t.description == "List items"
        assert t.input_schema == {"type": "object"}
        assert t.handler_name == "list_items"


class TestAgentAdapterABC:
    """AgentAdapter ABC — contract for all agent adapters."""

    def test_agent_adapter_importable(self) -> None:
        """RED: AgentAdapter is importable from apoch.adapters.base."""
        from apoch.adapters.base import AgentAdapter  # noqa: F401

    def test_agent_adapter_is_abstract(self) -> None:
        """AgentAdapter cannot be instantiated directly."""
        from apoch.adapters.base import AgentAdapter

        with pytest.raises(TypeError):
            AgentAdapter()  # type: ignore[abstract]

    def test_agent_adapter_has_abstract_methods(self) -> None:
        """AgentAdapter declares start, stop, health, register_module_tools as abstract."""
        from apoch.adapters.base import AgentAdapter

        assert "start" in AgentAdapter.__abstractmethods__
        assert "stop" in AgentAdapter.__abstractmethods__
        assert "health" in AgentAdapter.__abstractmethods__
        assert "register_module_tools" in AgentAdapter.__abstractmethods__

    def test_concrete_adapter_must_implement_all_methods(self) -> None:
        """A concrete adapter missing a method raises TypeError."""
        from apoch.adapters.base import AgentAdapter

        # Missing health
        with pytest.raises(TypeError):

            class _BadAdapter(AgentAdapter):  # type: ignore[abstract]
                async def start(self) -> None: ...
                async def stop(self) -> None: ...
                async def register_module_tools(self, module_name: str, module: object, tools: list) -> None: ...  # noqa: ARG002

            _BadAdapter(config={})

    def test_concrete_adapter_with_all_methods_instantiates(self) -> None:
        """A concrete adapter implementing all abstract methods can be instantiated."""
        from apoch.adapters.base import AgentAdapter

        class _GoodAdapter(AgentAdapter):
            async def start(self) -> None: ...
            async def stop(self) -> None: ...
            async def health(self): ...
            async def register_module_tools(self, module_name: str, module: object, tools: list) -> None: ...  # noqa: ARG002

        adapter = _GoodAdapter(config={})
        assert isinstance(adapter, AgentAdapter)

    def test_start_is_async(self) -> None:
        """AgentAdapter.start is an async method."""
        import asyncio

        from apoch.adapters.base import AgentAdapter

        class _TestAdapter(AgentAdapter):
            async def start(self) -> None: ...
            async def stop(self) -> None: ...
            async def health(self): ...
            async def register_module_tools(self, module_name: str, module: object, tools: list) -> None: ...  # noqa: ARG002

        adapter = _TestAdapter(config={})
        assert asyncio.iscoroutinefunction(adapter.start)
        assert asyncio.iscoroutinefunction(adapter.stop)
        assert asyncio.iscoroutinefunction(adapter.health)
        assert asyncio.iscoroutinefunction(adapter.register_module_tools)
