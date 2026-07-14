"""Tests for OpenCode Adapter.

Spec: agent-adapter §Module Tool Registration, §Gateway Health
Architecture: FastMCP encapsulated in adapters/opencode/ only.
"""

from __future__ import annotations

from typing import Any

import pytest


class _MockModule:
    """A minimal module-like object with public methods for tool testing."""

    def list_items(self, **kwargs: Any) -> dict:
        return {"action": "list_items", "kwargs": kwargs}

    def record(self, **kwargs: Any) -> dict:
        return {"action": "record", "kwargs": kwargs}

    def query(self, **kwargs: Any) -> dict:
        return {"action": "query", "kwargs": kwargs}

    def inspect(self, **kwargs: Any) -> dict:
        return {"action": "inspect", "kwargs": kwargs}

    def _private_method(self) -> str:
        return "secret"

    @property
    def not_callable(self) -> str:
        return "not a callable"


class _AsyncMockModule:
    """A module-like object with async handlers."""

    async def fetch(self, **kwargs: Any) -> dict:
        return {"action": "fetch", "kwargs": kwargs}

    async def process(self, **kwargs: Any) -> dict:
        return {"action": "process", "kwargs": kwargs}


class _FailingMockModule:
    """A module-like object whose handlers raise exceptions."""

    def crash(self, **kwargs: Any) -> dict:
        msg = "something went wrong"
        raise RuntimeError(msg)


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

    def _make_adapter(self) -> Any:
        from apoch.adapters.opencode.server import OpenCodeAdapter

        return OpenCodeAdapter(config={"name": "apoch"})

    def test_register_tool_adds_to_gateway(self) -> None:
        """Registering a tool adds it to _tool_registry."""
        import asyncio

        from apoch.adapters.base import ToolDef

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="list_items",
                    description="List all items",
                    input_schema={"type": "object"},
                    handler_name="list_items",
                ),
            ]
            await adapter.register_module_tools("chronicle", module, tools)
            assert "list_items" in adapter._tool_registry
            await adapter.stop()

        asyncio.run(_run())

    def test_register_multiple_modules(self) -> None:
        """Tools from different modules are all registered."""
        import asyncio

        from apoch.adapters.base import ToolDef

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "chronicle",
                module,
                [
                    ToolDef(name="record", description="Record an entry",
                            input_schema={}, handler_name="record"),
                    ToolDef(name="query", description="Query entries",
                            input_schema={}, handler_name="query"),
                ],
            )
            await adapter.register_module_tools(
                "vision",
                module,
                [
                    ToolDef(name="inspect", description="Inspect state",
                            input_schema={}, handler_name="inspect"),
                ],
            )
            assert "record" in adapter._tool_registry
            assert "query" in adapter._tool_registry
            assert "inspect" in adapter._tool_registry
            await adapter.stop()

        asyncio.run(_run())

    def test_duplicate_tool_names_get_prefixed(self) -> None:
        """Tool name collision across modules is handled by prefixing."""
        import asyncio

        from apoch.adapters.base import ToolDef

        adapter = self._make_adapter()
        mod_a = _MockModule()
        mod_b = _MockModule()

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "module_a",
                mod_a,
                [
                    ToolDef(name="status", description="Module A status",
                            input_schema={}, handler_name="list_items"),
                ],
            )
            await adapter.register_module_tools(
                "module_b",
                mod_b,
                [
                    ToolDef(name="status", description="Module B status",
                            input_schema={}, handler_name="list_items"),
                ],
            )
            assert "module_b_status" in adapter._tool_registry
            assert "status" in adapter._tool_registry or "module_a_status" in adapter._tool_registry
            await adapter.stop()

        asyncio.run(_run())

    def test_handler_not_found_raises(self) -> None:
        """Registering a tool with non-existent handler_name raises HANDLER_NOT_FOUND."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.core.exceptions import ToolExecutionError

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="bad_tool",
                    description="Non-existent handler",
                    input_schema={},
                    handler_name="does_not_exist",
                ),
            ]
            with pytest.raises(ToolExecutionError) as excinfo:
                await adapter.register_module_tools("test", module, tools)
            assert excinfo.value.code == ToolExecutionError.HANDLER_NOT_FOUND
            await adapter.stop()

        asyncio.run(_run())

    def test_private_handler_raises(self) -> None:
        """Registering a tool with private handler_name raises HANDLER_NOT_FOUND."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.core.exceptions import ToolExecutionError

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="secret_tool",
                    description="Private handler",
                    input_schema={},
                    handler_name="_private_method",
                ),
            ]
            with pytest.raises(ToolExecutionError) as excinfo:
                await adapter.register_module_tools("test", module, tools)
            assert excinfo.value.code == ToolExecutionError.HANDLER_NOT_FOUND
            await adapter.stop()

        asyncio.run(_run())

    def test_non_callable_handler_raises(self) -> None:
        """Registering a tool with non-callable handler raises HANDLER_NOT_FOUND."""
        import asyncio

        from apoch.adapters.base import ToolDef
        from apoch.core.exceptions import ToolExecutionError

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="prop_tool",
                    description="Property (not callable)",
                    input_schema={},
                    handler_name="not_callable",
                ),
            ]
            with pytest.raises(ToolExecutionError) as excinfo:
                await adapter.register_module_tools("test", module, tools)
            assert excinfo.value.code == ToolExecutionError.HANDLER_NOT_FOUND
            await adapter.stop()

        asyncio.run(_run())

    def test_registered_tool_creates_slot(self) -> None:
        """A successfully registered tool creates a _ToolSlot with handler + schema."""
        import asyncio

        from apoch.adapters.base import ToolDef

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="list_items",
                    description="List all items",
                    input_schema={"type": "object", "properties": {}},
                    handler_name="list_items",
                ),
            ]
            await adapter.register_module_tools("test", module, tools)
            slot = adapter._tool_registry.get("list_items")
            assert slot is not None
            assert slot.handler == module.list_items
            assert slot.schema == {"type": "object", "properties": {}}
            # Ensure module reference is NOT stored in the slot
            assert not hasattr(slot, "module")
            await adapter.stop()

        asyncio.run(_run())

    def test_stop_clears_registry(self) -> None:
        """Stopping the adapter clears _tool_registry."""
        import asyncio

        from apoch.adapters.base import ToolDef

        adapter = self._make_adapter()
        module = _MockModule()

        async def _run() -> None:
            await adapter.start()
            tools = [
                ToolDef(
                    name="list_items",
                    description="List all items",
                    input_schema={},
                    handler_name="list_items",
                ),
            ]
            await adapter.register_module_tools("test", module, tools)
            assert len(adapter._tool_registry) == 1
            await adapter.stop()
            assert len(adapter._tool_registry) == 0

        asyncio.run(_run())


class TestToolDispatch:
    """Tool dispatch via _dispatch()."""

    def _make_adapter(self) -> Any:
        from apoch.adapters.opencode.server import OpenCodeAdapter

        return OpenCodeAdapter(config={"name": "apoch"})

    def _register_tool(
        self,
        adapter: Any,
        module: Any,
        name: str = "test_tool",
        handler_name: str = "list_items",
        schema: dict | None = None,
    ) -> None:
        import asyncio

        from apoch.adapters.base import ToolDef

        async def _run() -> None:
            await adapter.start()
            await adapter.register_module_tools(
                "test",
                module,
                [
                    ToolDef(
                        name=name,
                        description="Test tool",
                        input_schema=schema or {"type": "object", "properties": {}},
                        handler_name=handler_name,
                    ),
                ],
            )

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_dispatch_valid_kwargs_returns_structured_response(self) -> None:
        """Valid kwargs return structured success response."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        self._register_tool(adapter, module)

        async def _run() -> None:
            result = await adapter._dispatch("test_tool", {"key": "value"})
            assert result == {
                "version": 1,
                "ok": True,
                "data": {"action": "list_items", "kwargs": {"key": "value"}},
            }
            await adapter.stop()

        asyncio.run(_run())

    def test_dispatch_no_kwargs_returns_structured_response(self) -> None:
        """Empty kwargs still produce a valid structured response."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        self._register_tool(adapter, module)

        async def _run() -> None:
            result = await adapter._dispatch("test_tool", {})
            assert result == {
                "version": 1,
                "ok": True,
                "data": {"action": "list_items", "kwargs": {}},
            }
            await adapter.stop()

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    def test_dispatch_invalid_kwargs_returns_validation_error(self) -> None:
        """Invalid kwargs against schema return VALIDATION_ERROR."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        self._register_tool(adapter, module, schema=schema)

        async def _run() -> None:
            result = await adapter._dispatch("test_tool", {})
            assert result["version"] == 1
            assert result["ok"] is False
            assert result["error"]["code"] == "VALIDATION_ERROR"
            await adapter.stop()

        asyncio.run(_run())

    def test_dispatch_wrong_type_kwargs_returns_validation_error(self) -> None:
        """Kwargs with wrong types return VALIDATION_ERROR."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
            "required": ["count"],
        }
        self._register_tool(adapter, module, schema=schema)

        async def _run() -> None:
            result = await adapter._dispatch("test_tool", {"count": "not_an_int"})
            assert result["version"] == 1
            assert result["ok"] is False
            assert result["error"]["code"] == "VALIDATION_ERROR"
            await adapter.stop()

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Tool not found
    # ------------------------------------------------------------------

    def test_dispatch_unknown_tool_returns_not_found(self) -> None:
        """Unknown tool name returns TOOL_NOT_FOUND."""
        import asyncio

        adapter = self._make_adapter()

        async def _run() -> None:
            await adapter.start()
            result = await adapter._dispatch("nonexistent_tool", {})
            assert result["version"] == 1
            assert result["ok"] is False
            assert result["error"]["code"] == "TOOL_NOT_FOUND"
            await adapter.stop()

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Sync vs async dispatch
    # ------------------------------------------------------------------

    def test_dispatch_sync_handler(self) -> None:
        """Sync handlers are dispatched correctly."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        self._register_tool(adapter, module)

        async def _run() -> None:
            result = await adapter._dispatch("test_tool", {"x": 1})
            assert result["ok"] is True
            assert result["data"] == {"action": "list_items", "kwargs": {"x": 1}}
            await adapter.stop()

        asyncio.run(_run())

    def test_dispatch_async_handler(self) -> None:
        """Async handlers are awaited correctly."""
        import asyncio

        adapter = self._make_adapter()
        module = _AsyncMockModule()
        self._register_tool(
            adapter,
            module,
            name="fetch_tool",
            handler_name="fetch",
        )

        async def _run() -> None:
            result = await adapter._dispatch("fetch_tool", {"id": 42})
            assert result["ok"] is True
            assert result["data"] == {"action": "fetch", "kwargs": {"id": 42}}
            await adapter.stop()

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Handler errors
    # ------------------------------------------------------------------

    def test_dispatch_handler_exception_returns_internal_error(self) -> None:
        """Handler that raises an exception returns INTERNAL_ERROR."""
        import asyncio

        adapter = self._make_adapter()
        module = _FailingMockModule()
        self._register_tool(
            adapter,
            module,
            name="crash_tool",
            handler_name="crash",
        )

        async def _run() -> None:
            result = await adapter._dispatch("crash_tool", {})
            assert result["version"] == 1
            assert result["ok"] is False
            assert result["error"]["code"] == "INTERNAL_ERROR"
            assert "RuntimeError" in result["error"]["message"]
            await adapter.stop()

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Stop clears registry
    # ------------------------------------------------------------------

    def test_dispatch_after_stop_returns_not_found(self) -> None:
        """After stop() clears the registry, dispatch returns TOOL_NOT_FOUND."""
        import asyncio

        adapter = self._make_adapter()
        module = _MockModule()
        self._register_tool(adapter, module)

        async def _run() -> None:
            await adapter.start()
            await adapter.stop()
            result = await adapter._dispatch("test_tool", {})
            assert result["ok"] is False
            assert result["error"]["code"] == "TOOL_NOT_FOUND"

        asyncio.run(_run())
