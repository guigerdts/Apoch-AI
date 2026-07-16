"""FastMCP gateway server for OpenCode integration.

Spec: agent-adapter §Module Tool Registration, §Gateway Health
Architecture: This module is the ONLY file that imports FastMCP.

Every public method is designed to be:
- Idempotent (start/stop can be called multiple times)
- Non-crashing (tool errors are caught, gateway stays healthy)
- Module-agnostic (no references to chronicle, guardian, vision, etc.)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import validate as js_validate
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import Field, create_model

from apoch.adapters.base import AgentAdapter, HealthStatus, ToolDef
from apoch.core.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


def _json_type_to_python(json_type: str) -> type:
    """Map a JSON Schema type name to the corresponding Python type."""
    mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    return mapping.get(json_type, str)


@dataclass
class _ToolSlot:
    """Internal slot tracking a registered tool's resolved handler.

    Attributes:
        handler: The resolved callable (``getattr(module, handler_name)``).
                 Must return ``dict | Awaitable[dict]``.
        schema:  The ``input_schema`` from the tool's ``ToolDef``.
    """

    handler: Callable[..., Any]
    schema: dict[str, Any]


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
        await adapter.register_module_tools("chronicle", module_instance, [...])
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
        # Runtime tool registry: tool_name → _ToolSlot
        self._tool_registry: dict[str, _ToolSlot] = {}

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

    async def serve(self) -> None:
        """Run the MCP gateway (blocking, stdio transport).

        Ensures the gateway is started (idempotent), then enters the
        stdio transport loop which blocks until cancelled.

        Raises:
            asyncio.CancelledError: On graceful shutdown (caller is
                expected to catch and handle cleanup).
        """
        await self.start()
        logger.info("OpenCode gateway entering stdio transport loop...")
        try:
            await self._server.run_stdio_async()
        except asyncio.CancelledError:
            logger.info("OpenCode gateway serve() cancelled — transport loop exiting")
            raise

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
        self._tool_registry.clear()
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

    async def register_module_tools(
        self,
        module_name: str,
        module: Any,
        tools: list[ToolDef],
    ) -> None:
        """Register *tools* belonging to *module_name* with the gateway.

        For each ``ToolDef``, resolves ``handler_name`` on *module* via
        ``getattr``.  If the handler does not exist, is private (``_``-prefixed),
        or is not callable, raises ``ToolExecutionError(HANDLER_NOT_FOUND)``
        and the tool is NOT registered — fail-fast at startup.
        """
        if self._server is None:
            logger.warning("Cannot register tools: gateway not started")
            return

        self._module_tools.setdefault(module_name, [])
        registered: list[str] = []

        for tool in tools:
            # Validate handler_name exists and is callable (fail-fast).
            self._validate_handler(module, tool)

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
                self._create_handler(final_name, tool.description),
                name=final_name,
                description=tool.description,
            )

            # Override FastMCP's auto-generated Pydantic arg_model. Without
            # this, the **kwargs handler signature generates a model dictating
            # a single "kwargs" field, which rejects all real call payloads.
            self._override_tool_arg_model(final_name, tool.input_schema)

            self._registered_names.add(final_name)
            self._module_tools[module_name].append(tool)

            # Store the resolved slot for dispatch (PR4B).
            self._tool_registry[final_name] = _ToolSlot(
                handler=getattr(module, tool.handler_name),
                schema=tool.input_schema,
            )
            registered.append(final_name)

        if registered:
            logger.info(
                "Registered %d tool(s) for module '%s': %s",
                len(registered),
                module_name,
                ", ".join(registered),
            )

    def _validate_handler(self, module: Any, tool: ToolDef) -> None:
        """Validate that *tool.handler_name* is a public callable on *module*.

        Raises:
            ToolExecutionError: If the handler is invalid.
        """
        name = tool.handler_name
        if name.startswith("_"):
            raise ToolExecutionError(
                code=ToolExecutionError.HANDLER_NOT_FOUND,
                message=f"Handler '{name}' is private (starts with '_'). "
                f"Only public methods are allowed as tool handlers.",
            )
        handler = getattr(module, name, None)
        if handler is None:
            raise ToolExecutionError(
                code=ToolExecutionError.HANDLER_NOT_FOUND,
                message=f"Handler '{name}' not found on module "
                f"'{type(module).__name__}'. Ensure the method exists "
                f"and is spelled correctly.",
            )
        if not callable(handler):
            raise ToolExecutionError(
                code=ToolExecutionError.HANDLER_NOT_FOUND,
                message=f"Handler '{name}' on module '{type(module).__name__}' is not callable.",
            )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, tool_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Resolve *tool_name*, validate kwargs, and dispatch to the handler.

        Returns the structured response envelope::

            {"version": 1, "ok": True, "data": <handler_result>}
            {"version": 1, "ok": False, "error": {"code": "...", "message": "..."}}
        """
        slot = self._tool_registry.get(tool_name)
        if slot is None:
            return {
                "version": 1,
                "ok": False,
                "error": {
                    "code": ToolExecutionError.TOOL_NOT_FOUND,
                    "message": f"Tool '{tool_name}' not found",
                },
            }

        # Strip None values: FastMCP inserts None for optional params the
        # user didn't provide, but jsonschema rejects None vs e.g. type:string.
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # Validate kwargs against JSON Schema.
        try:
            js_validate(instance=clean_kwargs, schema=slot.schema)
        except ValidationError as exc:
            return {
                "version": 1,
                "ok": False,
                "error": {
                    "code": ToolExecutionError.VALIDATION_ERROR,
                    "message": str(exc),
                },
            }
        except SchemaError as exc:
            return {
                "version": 1,
                "ok": False,
                "error": {
                    "code": ToolExecutionError.INTERNAL_ERROR,
                    "message": f"Schema error for '{tool_name}': {exc}",
                },
            }

        # Dispatch — sync or async (use cleaned kwargs so optional params
        # with a default are absent and fall through to their default).
        try:
            if inspect.iscoroutinefunction(slot.handler):
                result = await slot.handler(**clean_kwargs)
            else:
                result = slot.handler(**clean_kwargs)
        except ToolExecutionError as exc:
            return {
                "version": 1,
                "ok": False,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:
            logger.exception("Tool '%s' raised unexpected error", tool_name)
            return {
                "version": 1,
                "ok": False,
                "error": {
                    "code": ToolExecutionError.INTERNAL_ERROR,
                    "message": f"{type(exc).__name__}: {exc}",
                },
            }

        return {"version": 1, "ok": True, "data": result}

    def _create_handler(self, name: str, description: str) -> Any:
        """Create a FastMCP tool handler that routes through ``_dispatch``."""

        async def _handler(**kwargs: Any) -> dict[str, Any]:
            return await self._dispatch(name, kwargs)

        _handler.__name__ = name
        _handler.__doc__ = description
        return _handler

    def _override_tool_arg_model(self, tool_name: str, input_schema: dict) -> None:
        """Replace FastMCP's auto-generated arg model with one from *input_schema*.

        FastMCP generates a Pydantic model from the handler's ``**kwargs``
        signature, which creates a single required ``kwargs: str`` field that
        rejects real tool-call payloads.  We replace it with a proper model
        built from our ``ToolDef.input_schema`` so FastMCP validates correctly
        before our ``_dispatch`` runs its own jsonschema validation.
        """
        from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase  # noqa: PLC0415

        registered_tool = self._server._tool_manager._tools.get(tool_name)
        if registered_tool is None:
            return

        props = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))

        fields: dict[str, tuple[Any, Any]] = {}
        for prop_name, prop_schema in props.items():
            py_type = _json_type_to_python(prop_schema.get("type", "string"))
            if prop_name in required:
                fields[prop_name] = (py_type, Field(...))
            else:
                default = prop_schema.get("default", None)
                fields[prop_name] = (py_type | None, default)

        arg_model = create_model(
            f"{tool_name}Arguments",
            __base__=ArgModelBase,
            **fields,
        )

        registered_tool.parameters = input_schema
        registered_tool.fn_metadata.arg_model = arg_model

    # ------------------------------------------------------------------
    # Install / Uninstall (synchronous config management)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_apoch_command() -> list[str]:
        """Resolve the absolute path to the ``apoch`` CLI.

        Priority:
          1. Venv sibling of ``sys.executable`` — local venv (uv sync).
          2. ``shutil.which("apoch")`` — global install (pipx, uv tool).
          3. ``uv run`` — safety net if neither is available.
          4. Bare ``apoch`` — fallback with warning.
        """
        candidates: list[list[str]] = []

        # 1. Venv sibling  (sys.executable -> .venv/bin/python3 -> .venv/bin/apoch)
        venv_sibling = Path(sys.executable).parent / "apoch"
        if venv_sibling.exists():
            candidates.append([str(venv_sibling)])

        # 2. Global PATH
        global_path = shutil.which("apoch")
        if global_path:
            candidates.append([global_path])

        # 3. uv run as safety net
        uv_path = shutil.which("uv")
        if uv_path:
            candidates.append([uv_path, "run", "--directory", str(Path.cwd()), "apoch"])

        if not candidates:
            logger.warning(
                "Could not resolve apoch path — install may fail if "
                "apoch is not in $PATH"
            )
            return ["apoch"]

        chosen = candidates[0]
        logger.info("Resolved apoch command: %s", chosen)
        return chosen

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
        proposed = cfg.merge(current, self._resolve_apoch_command())
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
