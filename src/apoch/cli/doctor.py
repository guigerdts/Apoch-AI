"""apoch doctor — diagnostics for all registered adapters.

Spec: cli-interface §Doctor Diagnostics
Architecture: Iterates over ``registry.list_adapters()`` — adding a new
adapter automatically makes it visible to ``apoch doctor``.
"""

from __future__ import annotations

import asyncio

import typer

from apoch.adapters.registry import get_adapter, list_adapters

cli_app = typer.Typer()


@cli_app.callback(invoke_without_command=True)
def doctor() -> None:
    """Run diagnostics on all registered adapters.

    Reports health status, uptime, and any errors for each adapter.
    """
    names = list_adapters()
    if not names:
        typer.echo("No adapters registered.")
        raise typer.Exit()

    all_healthy = True

    for name in sorted(names):
        try:
            adapter = get_adapter(name)
            status = asyncio.run(adapter.health())
            if status.healthy:
                uptime = ""
                if status.uptime_seconds is not None:
                    uptime = f" (uptime: {status.uptime_seconds:.1f}s)"
                typer.secho(f"✓ {name}: healthy{uptime}", fg=typer.colors.GREEN)
            else:
                all_healthy = False
                error = status.error or "unknown error"
                typer.secho(f"✗ {name}: {error}", fg=typer.colors.RED)
        except Exception as exc:
            all_healthy = False
            typer.secho(f"✗ {name}: {exc}", fg=typer.colors.RED)

    if not all_healthy:
        raise SystemExit(1)
