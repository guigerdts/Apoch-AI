"""apoch install — install Apoch-AI into OpenCode's opencode.json.

Spec: cli-interface §Install Module
Architecture: CLI delegates to adapter — never imports OpenCodeConfig directly.
"""

from __future__ import annotations

import difflib
import json

import typer

from apoch.adapters.registry import get_adapter

cli_app = typer.Typer()


@cli_app.callback(invoke_without_command=True)
def install() -> None:
    """Install Apoch-AI into OpenCode configuration.

    Backs up opencode.json, computes the diff, asks for consent,
    and writes the merged configuration.
    """
    adapter = get_adapter("opencode")

    plan = adapter.prepare_install()

    # No changes needed
    if plan.current == plan.proposed:
        typer.echo("✓ Apoch-AI is already installed in opencode.json")
        adapter.discard_install(plan)
        raise typer.Exit()

    # Show diff
    current_str = json.dumps(plan.current, indent=2) if plan.current else "{}"
    proposed_str = json.dumps(plan.proposed, indent=2)
    diff_lines = list(
        difflib.unified_diff(
            current_str.splitlines(),
            proposed_str.splitlines(),
            fromfile="current",
            tofile="proposed",
            lineterm="",
        )
    )

    typer.echo("The following changes will be made to opencode.json:\n")
    for line in diff_lines:
        if line.startswith("+"):
            typer.secho(line, fg=typer.colors.GREEN)
        elif line.startswith("-"):
            typer.secho(line, fg=typer.colors.RED)
        elif line.startswith("@@"):
            typer.secho(line, fg=typer.colors.CYAN)
        else:
            typer.echo(line)

    # Ask for consent
    typer.echo()
    proceed = typer.confirm("Apply these changes?", default=True)
    if not proceed:
        adapter.discard_install(plan)
        typer.echo("Install cancelled.")
        raise typer.Exit()

    adapter.apply_install(plan)
    typer.echo("✓ Apoch-AI installed into OpenCode configuration")

    # Attempt to start the MCP gateway
    import asyncio

    try:
        asyncio.run(adapter.start())
        typer.echo("✓ MCP gateway started")
    except Exception as exc:
        typer.echo(f"⚠ Could not start MCP gateway: {exc}", err=True)
