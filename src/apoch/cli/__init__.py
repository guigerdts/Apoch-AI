"""CLI package — auto-discovery of command modules.

Design: Package Structure (cli/__init__.py, cli/app.py)
Architecture constraint: CLI must be extensible from plugins without
modifying app.py.  Adding a new command module to ``apoch/cli/`` is
sufficient — this module discovers it automatically.

Each command module (e.g. ``list.py``, ``status.py``) must expose a
``cli_app`` attribute that is a ``typer.Typer()`` instance.  The module's
stem name becomes the subcommand name.
"""

from __future__ import annotations

import importlib
import pkgutil
from importlib import metadata

import typer


def discover_and_register(main_app: typer.Typer) -> None:
    """Auto-discover command modules and register them as sub-typers.

    Scans every module in the ``apoch.cli`` package (excluding those
    whose name starts with ``_``).  If the module exposes a ``cli_app``
    :class:`typer.Typer` instance, it is registered as a sub-command
    named after the module's stem.

    Usage::

        app = typer.Typer()
        discover_and_register(app)
        # → ``apoch list``, ``apoch status`` are now available
    """
    import apoch.cli as _self

    # 1. Discover local command modules
    registered_names = set()
    for mod_info in pkgutil.iter_modules(_self.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"apoch.cli.{mod_info.name}")
        sub_app: object = getattr(mod, "cli_app", None)
        if sub_app is not None and isinstance(sub_app, typer.Typer):
            main_app.add_typer(sub_app, name=mod_info.name)
            registered_names.add(mod_info.name)

    # 2. Discover plugin commands via entry points
    try:
        eps = metadata.entry_points(group="apoch.cli")
    except TypeError:
        # Fallback for older Python versions
        eps = metadata.entry_points().get("apoch.cli", [])

    for ep in eps:
        if ep.name in registered_names:
            continue
        try:
            sub_app = ep.load()
            if isinstance(sub_app, typer.Typer):
                main_app.add_typer(sub_app, name=ep.name)
                registered_names.add(ep.name)
        except Exception:
            # Prevent plugin loading failures from breaking the CLI
            pass
