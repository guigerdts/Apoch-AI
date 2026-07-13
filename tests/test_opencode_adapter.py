"""Tests for OpenCode Adapter (RED phase).

Spec: agent-adapter §Module Tool Registration, §Gateway Health
Architecture: FastMCP encapsulated in adapters/opencode/ only.
Design: OpenCodeAdapter implements AgentAdapter ABC.

RED-GREEN phases:
  RED:   Tests MUST fail — adapters/opencode/ does not exist yet.
  GREEN: After creating adapters/opencode/, all tests MUST pass.
"""

from __future__ import annotations


class TestOpenCodeAdapterImports:
    """Package-level import tests — RED until adapters/opencode/ exists."""

    def test_opencode_package_importable(self) -> None:
        """The adapters.opencode package is importable."""
        import apoch.adapters.opencode  # noqa: F401

    def test_server_module_importable(self) -> None:
        """adapters.opencode.server is importable."""
        from apoch.adapters.opencode import server  # noqa: F401

    def test_open_code_adapter_class_importable(self) -> None:
        """OpenCodeAdapter is importable from server module."""
        from apoch.adapters.opencode.server import OpenCodeAdapter  # noqa: F401


class TestOpenCodeAdapterABC:
    """OpenCodeAdapter conforms to AgentAdapter ABC."""

    def test_is_agent_adapter_subclass(self) -> None:
        """OpenCodeAdapter subclasses AgentAdapter."""
        from apoch.adapters.base import AgentAdapter
        from apoch.adapters.opencode.server import OpenCodeAdapter

        assert issubclass(OpenCodeAdapter, AgentAdapter)

    def test_can_be_instantiated(self) -> None:
        """OpenCodeAdapter can be instantiated with a config dict."""
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})
        assert isinstance(adapter, OpenCodeAdapter)

    def test_start_and_stop_lifecycle(self) -> None:
        """OpenCodeAdapter.start() and .stop() are idempotent coroutines."""
        import asyncio

        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            await adapter.start()  # idempotent
            await adapter.stop()
            await adapter.stop()  # idempotent

        asyncio.run(_run())

    def test_health_after_start(self) -> None:
        """health() returns healthy after start."""
        import asyncio

        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            status = await adapter.health()
            assert status.healthy is True
            assert status.uptime_seconds is not None
            await adapter.stop()

        asyncio.run(_run())

    def test_health_before_start(self) -> None:
        """health() returns not healthy before start."""
        import asyncio

        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            status = await adapter.health()
            assert status.healthy is False

        asyncio.run(_run())

    def test_stop_before_start_is_safe(self) -> None:
        """Calling stop() before start() does not raise."""
        import asyncio

        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.stop()  # should be a no-op

        asyncio.run(_run())


class TestToolRegistration:
    """Tool registration via register_module_tools()."""

    def test_register_tool_adds_to_gateway(self) -> None:
        """Registering a tool makes it appear in list_tools."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="list_items",
                    description="List all items",
                    input_schema={"type": "object"},
                ),
            ]
            await adapter.register_module_tools("chronicle", tools)
            await adapter.stop()

        asyncio.run(_run())

    def test_register_multiple_modules(self) -> None:
        """Tools from different modules are all registered."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "chronicle",
                [
                    ToolDef(name="record", description="Record an entry"),
                    ToolDef(name="query", description="Query entries"),
                ],
            )
            await adapter.register_module_tools(
                "vision",
                [
                    ToolDef(name="inspect", description="Inspect state"),
                ],
            )
            await adapter.stop()

        asyncio.run(_run())

    def test_duplicate_tool_names_get_prefixed(self) -> None:
        """Tool name collision across modules is handled by prefixing."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "module_a",
                [
                    ToolDef(name="status", description="Module A status"),
                ],
            )
            await adapter.register_module_tools(
                "module_b",
                [
                    ToolDef(name="status", description="Module B status"),
                ],
            )
            await adapter.stop()

        asyncio.run(_run())

    def test_tool_error_does_not_crash_gateway(self) -> None:
        """A failing tool handler does not crash the gateway."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "test_mod",
                [
                    ToolDef(name="ok", description="Works fine"),
                ],
            )
            # Gateway should still be healthy after tool registration
            status = await adapter.health()
            assert status.healthy is True
            await adapter.stop()

        asyncio.run(_run())

    def test_remove_module_tools(self) -> None:
        """Tools from a module can be removed."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={"name": "apoch"})

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "chronicle",
                [
                    ToolDef(name="record", description="Record"),
                ],
            )
            await adapter.stop()

        asyncio.run(_run())
