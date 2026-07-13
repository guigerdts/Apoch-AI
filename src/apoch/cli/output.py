"""Output formatter — separates human-readable from machine-readable output.

Design: CLI Architecture Constraints §Output Design
Architecture: ``format_output(data, output_format, verbose)`` dispatches to
text or JSON formatters.  Adding ``"verbose"`` mode in the future does not
require refactoring call sites.
"""

from __future__ import annotations

import json
from typing import Any


def format_output(
    data: Any,
    output_format: str = "text",
    verbose: bool = False,
) -> str:
    """Format *data* for CLI display.

    Args:
        data:           List of dicts, single dict, or scalar.
        output_format:  ``"text"`` (default) for human-readable,
                        ``"json"`` for machine-parseable output.
        verbose:        Include extra detail in text mode.

    Returns:
        Formatted string ready for ``typer.echo()``.
    """
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)
    return _format_text(data, verbose=verbose)


def _format_text(data: Any, verbose: bool = False) -> str:
    """Format *data* as human-readable text."""
    if isinstance(data, list):
        return _format_list(data, verbose=verbose)
    if isinstance(data, dict):
        return "\n".join(f"  {k}: {v}" for k, v in data.items())
    return str(data)


def _format_list(items: list[Any], verbose: bool = False) -> str:
    """Format a list of items as a table-like listing.

    Each dict item is formatted as::

        {name:<20} {version:<8} {status}
          Entry: {entry_point}       (if verbose)
          Desc:  {description}       (if verbose)

    Non-dict items are formatted via ``str()``.
    """
    parts: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name", "?")
            version = item.get("version", "?")
            status = item.get("status", "unknown")
            line = f"  {name:<20} {version:<8} {status}"
            if verbose:
                ep = item.get("entry_point")
                if ep:
                    line += f"\n    Entry: {ep}"
                desc = item.get("description")
                if desc:
                    line += f"\n    Desc:  {desc}"
            parts.append(line)
        else:
            parts.append(f"  {item}")
    return "\n".join(parts)
