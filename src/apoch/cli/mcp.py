"""apoch mcp — manage the MCP gateway lifecycle.

Spec: agent-adapter §Gateway Health
Architecture: CLI delegates to adapter.start/stop — thin facade only.
"""

from __future__ import annotations

import asyncio

import typer

from apoch.adapters.registry import get_adapter

cli_app = typer.Typer()


@cli_app.command()
def start() -> None:
    """Start the MCP gateway."""
    adapter = get_adapter("opencode")
    try:
        asyncio.run(adapter.start())
        status = asyncio.run(adapter.health())
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
        asyncio.run(adapter.start())
        status = asyncio.run(adapter.health())
        if status.healthy:
            typer.echo("✓ MCP gateway restarted")
        else:
            typer.echo(f"⚠ MCP gateway restarted but unhealthy: {status.error}", err=True)
    except Exception as exc:
        typer.echo(f"✗ Failed to restart MCP gateway: {exc}", err=True)
        raise SystemExit(1)
