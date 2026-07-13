"""FastMCP gateway server for OpenCode integration.

Spec: agent-adapter §Module Tool Registration, §Gateway Health
Architecture: This module is the ONLY file that imports FastMCP.

Every public method is designed to be:
- Idempotent (start/stop can be called multiple times)
- Non-crashing (tool errors are caught, gateway stays healthy)
- Module-agnostic (no references to chronicle, guardian, vision, etc.)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apoch.adapters.base import AgentAdapter, HealthStatus, ToolDef

logger = logging.getLogger(__name__)


@dataclass
class InstallPlan:
    """Result of ``prepare_install()`` — describes what *would* change.

    Attributes:
        backup_path:    Path to the backup file created before any changes.
        current:        Current opencode.json content (may be empty).
        proposed:       Proposed content after merging the Apoch entry.
        backup_cleaned: Whether the backup was cleaned up (used by ``discard``).
    """

    backup_path: Path
    current: dict[str, Any] = field(default_factory=dict)
    proposed: dict[str, Any] = field(default_factory=dict)
    backup_cleaned: bool = False


class OpenCodeAdapter(AgentAdapter):
    """OpenCode adapter that wraps a FastMCP stdio gateway.

    Usage::

        adapter = OpenCodeAdapter(config={"name": "apoch"})
        await adapter.start()
        await adapter.register_module_tools("chronicle", [...])
        status = await adapter.health()
        await adapter.stop()
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._server: Any = None
        self._started_at: float | None = None
        self._module_tools: dict[str, list[ToolDef]] = {}
        # Track registered tool names to detect duplicates across modules
        self._registered_names: set[str] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the FastMCP gateway.

        Idempotent — subsequent calls are no-ops.
        """
        if self._server is not None:
            return
        from mcp.server.fastmcp import FastMCP

        name: str = self._config.get("name", "apoch")
        self._server = FastMCP(name, warn_on_duplicate_tools=False)
        self._started_at = time.monotonic()
        logger.info("OpenCode gateway started (name=%s)", name)

    async def stop(self) -> None:
        """Stop the FastMCP gateway.

        Idempotent — subsequent calls are no-ops.
        """
        if self._server is None:
            return
        self._server = None
        self._started_at = None
        self._module_tools.clear()
        self._registered_names.clear()
        logger.info("OpenCode gateway stopped")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> HealthStatus:
        """Return the current health status.

        A running gateway with a ``_server`` instance is considered healthy.
        """
        if self._server is None:
            return HealthStatus(healthy=False, error="gateway not started")
        uptime = time.monotonic() - self._started_at if self._started_at else None
        return HealthStatus(healthy=True, uptime_seconds=uptime)

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    async def register_module_tools(self, module_name: str, tools: list[ToolDef]) -> None:
        """Register *tools* belonging to *module_name*.

        If a tool name conflicts with a previously registered tool from
        another module, the new tool is prefixed with ``{module_name}_``
        and a warning is logged.
        """
        if self._server is None:
            logger.warning("Cannot register tools: gateway not started")
            return

        self._module_tools.setdefault(module_name, [])
        registered: list[str] = []

        for tool in tools:
            final_name = tool.name
            if tool.name in self._registered_names:
                final_name = f"{module_name}_{tool.name}"
                logger.warning(
                    "Tool '%s' from module '%s' renamed to '%s' (duplicate)",
                    tool.name,
                    module_name,
                    final_name,
                )

            self._server.add_tool(
                _make_tool_handler(final_name, tool.description),
                name=final_name,
                description=tool.description,
            )
            self._registered_names.add(final_name)
            self._module_tools[module_name].append(tool)
            registered.append(final_name)

        if registered:
            logger.info(
                "Registered %d tool(s) for module '%s': %s",
                len(registered),
                module_name,
                ", ".join(registered),
            )

    # ------------------------------------------------------------------
    # Install / Uninstall (synchronous config management)
    # ------------------------------------------------------------------

    def prepare_install(self) -> InstallPlan:
        """Back up current config and compute the proposed change.

        Returns an ``InstallPlan`` with the backup path, current content,
        and proposed content.  The CLI is expected to present the diff
        to the user and call ``apply_install()`` or ``discard_install()``.

        The adapter owns all ``OpenCodeConfig`` interaction — the CLI
        never imports it.
        """
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        current = cfg.read()
        proposed = cfg.merge(current)
        backup_path = cfg.backup()
        return InstallPlan(backup_path=backup_path, current=current, proposed=proposed)

    def apply_install(self, plan: InstallPlan) -> None:
        """Persist the proposed config from *plan*.

        Writes the proposed content to opencode.json using an atomic
        write.  This is a synchronous file operation — no gateway
        lifecycle involved.
        """
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        cfg.write(plan.proposed)
        logger.info("Install applied — opencode.json updated")

    def discard_install(self, plan: InstallPlan) -> None:
        """Remove the backup file created during *plan* preparation.

        Called when the user declines to proceed with the install.
        """
        if plan.backup_cleaned:
            return
        try:
            plan.backup_path.unlink(missing_ok=True)
            plan.backup_cleaned = True
            logger.info("Install discarded — backup removed: %s", plan.backup_path)
        except OSError:
            logger.warning("Could not remove backup: %s", plan.backup_path)

    def uninstall(self) -> None:
        """Restore opencode.json from the most recent backup.

        Uses ``OpenCodeConfig.rollback()`` with the latest timestamped
        backup file, then discards the backup.
        """
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        # Find latest backup
        backup_dir = cfg._backup_dir  # type: ignore[attr-defined]
        if not backup_dir.exists():
            logger.info("No backups found — nothing to uninstall")
            return

        backups = sorted(backup_dir.glob("opencode-*.json"))
        if not backups:
            logger.info("No backups found — nothing to uninstall")
            return

        latest = backups[-1]
        cfg.rollback(latest)
        latest.unlink()
        logger.info("Uninstall complete — restored from: %s", latest)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _make_tool_handler(name: str, description: str) -> Any:
    """Create a no-op tool handler for the given *name*.

    In v1 these handlers are placeholder stubs — real module tool
    dispatch will be wired in PR4–PR6.
    """

    async def _handler(**kwargs: Any) -> str:
        return f"{name}: called with {kwargs}"

    # Attach metadata for FastMCP's introspection
    _handler.__name__ = name
    _handler.__doc__ = description
    return _handler
