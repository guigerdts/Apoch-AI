"""apoch uninstall — remove Apoch-AI from OpenCode configuration.

Spec: cli-interface §Uninstall
Architecture: CLI delegates to adapter — never imports OpenCodeConfig directly.
"""

from __future__ import annotations

import typer

from apoch.adapters.registry import get_adapter

cli_app = typer.Typer()


@cli_app.callback(invoke_without_command=True)
def uninstall() -> None:
    """Remove Apoch-AI from OpenCode configuration.

    Restores opencode.json from the most recent backup created
    during ``apoch install``.
    """
    adapter = get_adapter("opencode")

    proceed = typer.confirm(
        "This will restore opencode.json from the last backup. Continue?",
        default=False,
    )
    if not proceed:
        typer.echo("Uninstall cancelled.")
        raise typer.Exit()

    adapter.uninstall()
    typer.echo("✓ Apoch-AI removed from OpenCode configuration")
