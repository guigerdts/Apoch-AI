"""CLI application — typer app, command tree, and error handling.

Design: Package Structure (cli/app.py)
Architecture: CLI is a thin presentation layer — no business logic.

This module:
1. Creates the main :class:`typer.Typer` ``app``.
2. Auto-discovers subcommand modules via :func:`discover_and_register`.
3. Provides ``entry_point()`` as the console-scripts callable with
   error handling (``ApochError`` → exit code 1).
"""

from __future__ import annotations

import typer

from apoch import __version__
from apoch.cli import discover_and_register
from apoch.core.exceptions import ApochError

# ---------------------------------------------------------------------------
# Main typer app
# ---------------------------------------------------------------------------

app = typer.Typer(pretty_exceptions_enable=False)

# Auto-discover subcommand modules (list, status, …)
discover_and_register(app)


# ---------------------------------------------------------------------------
# Global callback
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    """Print version and exit when ``--version`` is passed."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the Apoch-AI version and exit.",
    ),
) -> None:
    """Apoch-AI: Agent-agnostic framework for AI-assisted development workflows."""


# ---------------------------------------------------------------------------
# Entry point with error handling
# ---------------------------------------------------------------------------


def entry_point() -> None:
    """Run the CLI application with domain-error handling.

    Catches :exc:`ApochError` and translates to a friendly message
    with exit code 1.  Unknown subcommands are handled natively by
    typer/click (exit code 2).
    """
    try:
        app()
    except ApochError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise SystemExit(1)
