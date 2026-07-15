"""apoch stack — manage platform component lifecycle.

Architecture: Thin CLI adapter.  Parses arguments, delegates to
``StackManager``, formats results.  Zero business logic.
"""

from __future__ import annotations

import asyncio

import typer

from apoch.stack import StackManager, create_manager
from apoch.stack.state import StackState

cli_app = typer.Typer(help="Manage platform stack components")


# ── Helpers ──────────────────────────────────────────────────────────


def _state_color(state: StackState) -> str:
    """Return the typer color for a given *state*."""
    if state in (StackState.INSTALLED, StackState.ACTIVE, StackState.INACTIVE):
        return typer.colors.GREEN
    if state in (
        StackState.UNKNOWN,
        StackState.NOT_INSTALLED,
        StackState.OUTDATED,
        StackState.UNSUPPORTED,
    ):
        return typer.colors.YELLOW
    return typer.colors.RED  # ERROR, BROKEN


def _render_component(manager: StackManager) -> None:
    """Print every component as a block.

    Format per component::

        Name (kind)
          State:       <state>
          Version:     <version>
          Project:     <homepage>
          Repository:  <repository>
          Docs:        <docs_url>
          Install:     <install_command>
    """
    for name, status in sorted(manager.list_components().items()):
        desc = status.descriptor
        info = status.info
        state = status.state

        # Header
        typer.echo(f"{desc.name} ({desc.kind})")

        if state is StackState.OUTDATED:
            installed_ver = info.version if info and info.version else "—"
            typer.echo(f"  {'Installed:':<13}{installed_ver}")
            if desc.min_version:
                typer.echo(f"  {'Required:':<13}>={desc.min_version}")

        # State (colored)
        typer.secho(f"  {'State:':<13}{state.value.upper()}", fg=_state_color(state))

        if state is not StackState.OUTDATED:
            if state is StackState.NOT_INSTALLED:
                typer.echo(f"  {'Version:':<13}—")
            else:
                ver = info.version if info and info.version else "—"
                typer.echo(f"  {'Version:':<13}{ver}")

        # Links (only when the descriptor field is non-empty)
        if desc.homepage:
            typer.echo(f"  {'Project:':<13}{desc.homepage}")
        if desc.repository:
            typer.echo(f"  {'Repository:':<13}{desc.repository}")
        if desc.docs_url:
            typer.echo(f"  {'Docs:':<13}{desc.docs_url}")

        # Install / Update command
        if state is StackState.NOT_INSTALLED and desc.install_command:
            typer.echo(f"  {'Install:':<13}{desc.install_command}")
        elif state is StackState.OUTDATED and desc.install_command:
            typer.echo(f"  {'Update:':<13}{desc.install_command}")
        elif (
            state in (StackState.ERROR, StackState.BROKEN, StackState.UNSUPPORTED)
            and desc.install_command
        ):
            typer.echo(f"  {'Install:':<13}{desc.install_command}")

        typer.echo()


def _format_result(
    component: str,
    success: bool,
    message: str,
) -> None:
    """Print a single operation result line."""
    icon = "✓" if success else "✗"
    color = typer.colors.GREEN if success else typer.colors.RED
    typer.secho(f"  {icon} {component}: {message}", fg=color)


def _exit_code(results: list[bool]) -> None:
    """Exit with 1 if any operation failed."""
    if not all(results):
        raise typer.Exit(code=1)


# ── Commands ─────────────────────────────────────────────────────────


@cli_app.command()
def status() -> None:
    """Show the state of every registered stack component."""
    manager = create_manager()
    manager.refresh_sync()
    components = manager.list_components()

    if not components:
        typer.echo("No stack components registered.")
        raise typer.Exit()

    _render_component(manager)


@cli_app.command()
def install(
    components: list[str] = typer.Argument(
        None,
        help="Components to install (default: all registered)",
    ),
) -> None:
    """Install stack components (one or all)."""
    manager = create_manager()
    targets = components or sorted(manager.list_components().keys())

    if not targets:
        typer.echo("No components to install.")
        raise typer.Exit()

    results: list[bool] = []
    for name in targets:
        result = asyncio.run(manager.install(name))
        _format_result(name, result.success, result.message)
        results.append(result.success)

    _exit_code(results)


@cli_app.command()
def uninstall(
    components: list[str] = typer.Argument(
        None,
        help="Components to uninstall (default: all registered)",
    ),
) -> None:
    """Uninstall stack components (one or all)."""
    manager = create_manager()
    targets = components or sorted(manager.list_components().keys())

    if not targets:
        typer.echo("No components to uninstall.")
        raise typer.Exit()

    results: list[bool] = []
    for name in targets:
        result = asyncio.run(manager.uninstall(name))
        _format_result(name, result.success, result.message)
        results.append(result.success)

    _exit_code(results)


@cli_app.command()
def verify(
    components: list[str] = typer.Argument(
        None,
        help="Components to verify (default: all registered)",
    ),
    skip_async: bool = typer.Option(
        False,
        "--skip-async",
        help="Skip long-running remote checks",
    ),
) -> None:
    """Verify installation of stack components."""
    manager = create_manager()
    targets = components or sorted(manager.list_components().keys())

    if not targets:
        typer.echo("No components to verify.")
        raise typer.Exit()

    results: list[bool] = []
    for name in targets:
        result = asyncio.run(manager.verify(name, skip_async=skip_async))
        _format_result(name, result.success, result.message)
        results.append(result.success)

    _exit_code(results)
