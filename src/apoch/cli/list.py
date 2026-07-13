"""``apoch list`` — list all modules and their states.

Design: Subcommand Matrix (list → ModuleRegistry.discover())
Spec: cli-interface §List Modules

Delegates to :class:`apoch.core.registry.ModuleRegistry` for both
discovery and loaded-state inspection.  Zero business logic.
"""

from __future__ import annotations

import typer

from apoch.cli.output import format_output
from apoch.core.registry import ModuleRegistry

cli_app = typer.Typer()


@cli_app.callback(invoke_without_command=True)
def list_cmd(
    verbose: bool = typer.Option(
        False, "--verbose", help="Show detailed module info (entry point, description)."
    ),
    fmt: str = typer.Option(
        "text", "--format", help="Output format: text or json."
    ),
) -> None:
    """List all discovered modules and their states.

    Delegates to ModuleRegistry.discover() for metadata and
    ModuleRegistry.loaded for current module state.
    """
    registry = ModuleRegistry(config={})
    discovered = registry.discover()
    loaded = registry.loaded

    rows: list[dict] = []
    for meta in discovered:
        mod = loaded.get(meta.name)
        status: str = mod.state.value if mod else "unknown"

        row: dict = {
            "name": meta.name,
            "version": meta.version,
            "status": status,
            "entry_point": meta.entry_point,
        }
        if verbose:
            row["description"] = meta.description
        rows.append(row)

    output = format_output(rows, output_format=fmt, verbose=verbose)
    typer.echo(output)
