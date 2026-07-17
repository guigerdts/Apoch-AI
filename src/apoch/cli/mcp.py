"""apoch mcp — manage the MCP gateway lifecycle.

Spec: agent-adapter §Gateway Health
Architecture: CLI delegates to AgentAdapterManager — thin facade only.
"""

from __future__ import annotations

import asyncio

import typer

from apoch.adapters.manager import AgentAdapterManager
from apoch.adapters.registry import get_adapter
from apoch.core.registry import ModuleRegistry

cli_app = typer.Typer(
    help="Manage the MCP gateway lifecycle: start, stop, serve, restart.",
)


def _build_manager() -> AgentAdapterManager:
    """Build an AgentAdapterManager with the default adapter and registry."""
    adapter = get_adapter("opencode")
    registry = ModuleRegistry(config={})
    return AgentAdapterManager(adapter=adapter, registry=registry)


@cli_app.command()
def serve() -> None:
    """Run the MCP gateway (blocking, stdio transport)."""
    manager = _build_manager()
    try:
        asyncio.run(manager.serve())
    except KeyboardInterrupt:
        typer.echo()
        typer.echo("MCP gateway stopped")
        raise SystemExit(0)


@cli_app.command()
def start() -> None:
    """Start the MCP gateway with module tool registration."""
    manager = _build_manager()
    try:
        asyncio.run(manager.start())
        status = asyncio.run(manager._adapter.health())
        if status.healthy:
            typer.echo("✓ MCP gateway started")
        else:
            typer.echo(f"⚠ MCP gateway did not become healthy: {status.error}", err=True)
    except Exception as exc:
        typer.echo(f"✗ Failed to start MCP gateway: {exc}", err=True)
        raise SystemExit(1)


@cli_app.command()
def stop() -> None:
    """Stop the MCP gateway."""
    adapter = get_adapter("opencode")
    try:
        asyncio.run(adapter.stop())
        typer.echo("✓ MCP gateway stopped")
    except Exception as exc:
        typer.echo(f"✗ Failed to stop MCP gateway: {exc}", err=True)
        raise SystemExit(1)


@cli_app.command()
def restart() -> None:
    """Restart the MCP gateway (stop then start)."""
    adapter = get_adapter("opencode")
    try:
        asyncio.run(adapter.stop())
    except Exception:
        pass  # May not be running — that's fine.
    manager = _build_manager()
    try:
        asyncio.run(manager.start())
        status = asyncio.run(manager._adapter.health())
        if status.healthy:
            typer.echo("✓ MCP gateway restarted")
        else:
            typer.echo(f"⚠ MCP gateway restarted but unhealthy: {status.error}", err=True)
    except Exception as exc:
        typer.echo(f"✗ Failed to restart MCP gateway: {exc}", err=True)
        raise SystemExit(1)
