"""``apoch status`` — system health and gateway status.

Design: Subcommand Matrix (status → Engine engine info + ModuleRegistry stats)
Spec: cli-interface §Public Interfaces, §List Modules

Delegates to :class:`apoch.core.registry.ModuleRegistry` for module
discovery counts.  Zero business logic.
"""

from __future__ import annotations

import typer

from apoch import __version__
from apoch.cli.output import format_output
from apoch.core.registry import ModuleRegistry

cli_app = typer.Typer()


@cli_app.callback(invoke_without_command=True)
def status_cmd(
    fmt: str = typer.Option("text", "--format", help="Output format: text or json."),
) -> None:
    """Show system health and module status.

    Displays version, discovered module count, and loaded module
    count.  Delegates to ModuleRegistry for discovery and state.
    """
    registry = ModuleRegistry(config={})
    discovered = registry.discover()
    loaded = registry.loaded

    data = {
        "version": __version__,
        "discovered_modules": len(discovered),
        "loaded_modules": len(loaded),
    }
    output = format_output(data, output_format=fmt)
    typer.echo(output)
