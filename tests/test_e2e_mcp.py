"""E2E smoke test — validates the MCP tool runtime against a real FastMCP server.

This test launches the full Apoch-AI stack as a subprocess (engine + adapter +
module tools) and connects via the MCP stdio client protocol. It verifies:

  1. Tool discovery — the client sees all expected tools
  2. Tool invocation — each module's tools can be called
  3. Schema validation — invalid kwargs return VALIDATION_ERROR
  4. Error handling — unknown tools return TOOL_NOT_FOUND

Gate: This is a pre-PR5 validation gate, NOT a feature PR.
If this test passes, the PR4 runtime is confirmed working on real MCP protocol.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult

# ---------------------------------------------------------------------------
# Tool names
# ---------------------------------------------------------------------------

EXPECTED_TOOLS = frozenset({
    # Public MCP tools (PR2–PR8)
    "apoch_status",
    "apoch_health",
    "apoch_history",
    "apoch_recommend",
    "apoch_progress",
    "apoch_insights",
    "apoch_logs",
    # Legacy aliases (PR9)
    "vision_state",
    "chronicle_query",
    "guardian_diagnostics",
    "guardian_all_diagnostics",
    "vision_logs",
})

SAFE_TOOLS: dict[str, dict[str, Any]] = {
    "apoch_status": {},
    "apoch_health": {},
    "apoch_recommend": {},
    "apoch_progress": {},
    "apoch_insights": {},
    # Legacy aliases (PR9) — safe, no side effects
    "vision_state": {},
    "guardian_all_diagnostics": {},
    "vision_logs": {},
}

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "tests._mcp_e2e_server"],
)


@asynccontextmanager
async def _suppress_anyio_cancel_scope():
    """Suppress anyio's cancel-scope cross-task RuntimeError.

    Known incompatibility between anyio TaskGroup and pytest-asyncio:
    when the module-scoped fixture tears down, the cancel scope's exit
    runs in a different asyncio task than its enter — anyio raises.
    The subprocess is already dead at this point so it's safe to ignore.
    """
    try:
        yield
    except RuntimeError as exc:
        if "cancel scope" in str(exc):
            pass
        else:
            raise


# ---------------------------------------------------------------------------
# Module-scoped fixture — one connection for all tests in this module.
# The stdio_client context manager runs entirely inside the fixture, so
# anyio's cancel scopes stay tied to the correct task throughout setup
# and teardown.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def mcp_session() -> ClientSession:
    """Connect to the MCP E2E server and return an initialized session."""
    async with _suppress_anyio_cancel_scope():
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with _suppress_anyio_cancel_scope():
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session


# ---------------------------------------------------------------------------
# Tests: Tool Discovery
# ---------------------------------------------------------------------------


class TestToolDiscovery:
    """Verify all expected tools appear in the capabilities list."""

    async def test_list_tools_returns_all_expected(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.list_tools()
        tool_names = {t.name for t in result.tools}
        missing = EXPECTED_TOOLS - tool_names
        assert not missing, f"Missing tools: {missing}"

    async def test_no_duplicate_tools(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.list_tools()
        names = [t.name for t in result.tools]
        duplicates = {n for n in names if names.count(n) > 1}
        assert not duplicates, f"Duplicate tool names: {duplicates}"

    async def test_each_tool_has_description(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.list_tools()
        empty = [t.name for t in result.tools if not t.description]
        assert not empty, f"Tools with empty descriptions: {empty}"

    async def test_each_tool_has_input_schema(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.list_tools()
        for tool in result.tools:
            schema = tool.inputSchema
            assert "type" in schema, f"Tool '{tool.name}' has no type in schema"
            assert schema["type"] == "object"


# ---------------------------------------------------------------------------
# Tests: Tool Invocation
# ---------------------------------------------------------------------------


class TestToolInvocation:
    """Verify tools execute and return structured responses."""

    async def test_call_safe_tools_returns_structured_response(
        self, mcp_session: ClientSession
    ) -> None:
        for tool_name, kwargs in SAFE_TOOLS.items():
            result: CallToolResult = await mcp_session.call_tool(tool_name, kwargs)
            assert result.isError is False, (
                f"Tool '{tool_name}' returned isError=True: {result.content}"
            )
            assert result.content, f"Tool '{tool_name}' returned empty content"

    async def test_legacy_alias_vision_state(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.call_tool("vision_state", {})
        assert result.isError is False
        assert result.content is not None

    async def test_legacy_alias_guardian_diagnostics(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.call_tool(
            "guardian_diagnostics",
            {"module_name": "ChronicleModule"},
        )
        assert result.isError is False


# ---------------------------------------------------------------------------
# Tests: Schema Validation
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Verify invalid kwargs return validation errors from the server."""

    async def test_required_field_missing(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.call_tool("guardian_diagnostics", {})
        assert result.isError is True

    async def test_wrong_type_kwarg(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.call_tool(
            "guardian_diagnostics",
            {"module_name": 12345},
        )
        assert result.isError is True


# ---------------------------------------------------------------------------
# Tests: Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify error responses for edge cases like unknown tools."""

    async def test_unknown_tool_returns_error(self, mcp_session: ClientSession) -> None:
        result = await mcp_session.call_tool("nonexistent_tool", {})
        assert result.isError is True
