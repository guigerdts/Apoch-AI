"""MCP E2E test server — starts full Apoch-AI stack and serves via stdio.

Usage:
    uv run python -m tests._mcp_e2e_server

This script is launched as a subprocess by test_e2e_mcp.py.
It:
  1. Creates the OpenCode adapter (FastMCP server)
  2. Starts the Engine (discovers + loads chronicle, guardian, vision)
  3. Registers all module tools with the adapter
  4. Calls run_stdio_async() to serve requests over stdio

The server runs until the client disconnects or stdin closes.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from apoch.adapters.manager import AgentAdapterManager
from apoch.adapters.registry import get_adapter
from apoch.core.registry import ModuleRegistry

logger = logging.getLogger(__name__)


async def main() -> None:
    """Start the full Apoch-AI stack and serve MCP requests via stdio."""
    adapter = get_adapter("opencode")
    registry = ModuleRegistry(config={})
    manager = AgentAdapterManager(adapter=adapter, registry=registry)

    try:
        await manager.start()
    except Exception:
        logger.exception("Server startup failed")
        sys.exit(1)

    # Serve requests over stdio — blocks until client disconnects.
    await adapter._server.run_stdio_async()  # type: ignore[union-attr]


if __name__ == "__main__":
    asyncio.run(main())
