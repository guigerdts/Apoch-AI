"""CodeGraph Stack Component — adapter to the official CodeGraph CLI.

Apoch does **not** implement CodeGraph.  It acts as an adapter to the
official project at https://colbymchenry.github.io/codegraph/ using its
public CLI.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
Spec: codegraph-component
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.result import OperationResult
from apoch.stack.runner import CommandRunner, RealRunner

log = logging.getLogger(__name__)

# ── Descriptor ─────────────────────────────────────────────────────────

CODEGRAPH_DESCRIPTOR = StackDescriptor(
    id="codegraph",
    name="CodeGraph",
    kind="integrations",
    version="1.4.1",
    description="Code intelligence knowledge graph for AI coding agents",
    entry_point="apoch.stack.components.codegraph:CodeGraphComponent",
    install_command="npm install -g @colbymchenry/codegraph",
    install_manager="npm",
    homepage="https://colbymchenry.github.io/codegraph/",
    repository="https://github.com/colbymchenry/codegraph",
    docs_url="https://colbymchenry.github.io/codegraph/",
    requires=("node",),
    capabilities=("code-intelligence", "knowledge-graph", "mcp"),
)


# ── Version regex ──────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)", re.MULTILINE)


def _parse_version(output: str) -> str | None:
    """Extract a semantic version from *output*.

    Handles formats like ``"1.3.1"`` and ``"v1.3.1"``.  Returns ``None``
    when no version can be parsed.
    """
    if match := _VERSION_RE.search(output):
        return match.group(1)
    log.warning("Could not parse CodeGraph version from output: %r", output[:200])
    return None


# ── Component ──────────────────────────────────────────────────────────


class CodeGraphComponent(StackComponent):
    """Adapter for the official CodeGraph CLI.

    All lifecycle methods delegate to the official ``codegraph`` npm
    package via :class:`CommandRunner`.  No internal reimplementation.
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        """Initialise with an optional custom *runner* (injectable for tests)."""
        self._runner = runner or RealRunner()

    @property
    def descriptor(self) -> StackDescriptor:
        """Return the static :data:`CODEGRAPH_DESCRIPTOR` for CodeGraph."""
        return CODEGRAPH_DESCRIPTOR

    # ── Lifecycle: detect ─────────────────────────────────────────────

    async def detect(self) -> ComponentInfo:
        """Locate the ``codegraph`` binary and parse its version.

        Returns:
            ``ComponentInfo(installed=True, version=..., executable_path=...)``
            when the binary is found and its version parses correctly.
            ``ComponentInfo(installed=False)`` when the binary is not on
            ``$PATH`` or when the CLI invocation fails.
        """
        binary = shutil.which("codegraph")
        if binary is None:
            log.info("CodeGraph binary not found on PATH")
            return ComponentInfo(installed=False)

        result = await self._runner.run(["codegraph", "--version"])
        if result.returncode != 0:
            log.warning(
                "codegraph --version exited with code %s: %s",
                result.returncode,
                result.stderr[:200],
            )
            return ComponentInfo(
                installed=False,
                metadata={"error": f"version check failed: {result.stderr[:200]}"},
            )

        version = _parse_version(result.stdout)
        return ComponentInfo(
            installed=True,
            version=version,
            executable_path=Path(binary),
        )

    # ── Lifecycle: install ────────────────────────────────────────────

    async def install(self) -> OperationResult:
        """Install CodeGraph via npm.

        Prerequisites: Node.js (any version).
        """
        log.info("CodeGraph install starting")
        cmd = ["npm", "install", "-g", "@colbymchenry/codegraph"]
        log.info("Install command: %s", " ".join(cmd))

        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error(
                "CodeGraph install failed: %s",
                result.stderr[:500],
            )
            return OperationResult(
                success=False,
                component="codegraph",
                message=f"Installation failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        # Confirm installation — binary must be present on PATH
        info = await self.detect()
        if info.installed:
            log.info("CodeGraph installed successfully (version=%s)", info.version)
            return OperationResult(
                success=True,
                component="codegraph",
                message=f"CodeGraph {info.version or ''} installed".strip(),
            )

        log.warning("Install command succeeded but CodeGraph binary not found after install")
        return OperationResult(
            success=False,
            component="codegraph",
            message="Install completed but CodeGraph binary not found on PATH",
            details={"command": cmd},
        )

    # ── Lifecycle: verify ─────────────────────────────────────────────

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Verify CodeGraph installation.

        Two-phase check:
          1. Call ``detect()`` to observe the local installation.
          2. Run ``codegraph --help`` as a basic responsiveness check.

        Note: CodeGraph has no ``doctor`` command — ``--help`` is the
        closest functional check available (Context7 pattern).
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="codegraph",
                message="CodeGraph is not installed",
            )

        # Basic responsiveness check (no doctor command available)
        result = await self._runner.run(["codegraph", "--help"])
        if result.returncode != 0:
            log.warning(
                "CodeGraph verify — --help failed (exit %s): %s",
                result.returncode,
                result.stderr[:200],
            )
            return OperationResult(
                success=False,
                component="codegraph",
                message=f"codegraph --help failed (exit {result.returncode})",
                details={"help_exit": result.returncode},
            )

        return OperationResult(
            success=True,
            component="codegraph",
            message=f"CodeGraph {info.version or ''} verified".strip(),
            details={"version": info.version},
        )

    # ── Lifecycle: activate / deactivate ──────────────────────────────

    async def activate(self) -> OperationResult:
        """Activate CodeGraph.

        Verifies that the binary is installed and operational.
        CodeGraph is a CLI binary — no session state to configure.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="codegraph",
                message="CodeGraph is not installed — install it first",
            )
        return OperationResult(
            success=True,
            component="codegraph",
            message=f"CodeGraph {info.version or ''} active".strip(),
        )

    async def deactivate(self) -> OperationResult:
        """Deactivate CodeGraph.

        No-op — CodeGraph is a CLI binary with no persistent session.
        """
        return OperationResult(
            success=True,
            component="codegraph",
            message="CodeGraph deactivated",
        )

    # ── Lifecycle: uninstall ──────────────────────────────────────────

    async def uninstall(self) -> OperationResult:
        """Uninstall CodeGraph via npm."""
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=True,
                component="codegraph",
                message="CodeGraph is not installed",
            )

        cmd = ["npm", "uninstall", "-g", "@colbymchenry/codegraph"]
        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error("CodeGraph uninstall failed: %s", result.stderr[:200])
            return OperationResult(
                success=False,
                component="codegraph",
                message=f"Uninstall failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        log.info("CodeGraph uninstalled successfully")
        return OperationResult(
            success=True,
            component="codegraph",
            message="CodeGraph uninstalled",
        )

    # ── Lifecycle: health ─────────────────────────────────────────────

    async def health(self) -> dict:
        """Return a health status dict for CodeGraph.

        Strategy (JSON-first with exit-code fallback):
          1. Call ``self.detect()`` to check binary presence.
          2. Run ``codegraph status --json`` and parse the JSON.
          3. If valid JSON → ``"healthy"`` with full JSON as diagnostics.
          4. If JSON unparseable → fallback to exit code.
          5. Never throw — degrade gracefully on parse errors.
        """
        info = await self.detect()
        if not info.installed:
            return {
                "status": "down",
                "component": "codegraph",
                "version": None,
            }

        # Try JSON mode first
        result = await self._runner.run(["codegraph", "status", "--json"])
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    return {
                        "status": "healthy",
                        "component": "codegraph",
                        "version": info.version,
                        "diagnostics": data,
                    }
            except json.JSONDecodeError:
                log.warning(
                    "Failed to parse 'codegraph status --json'; falling back to exit code"
                )

        # Fallback: exit code only
        if result.returncode == 0:
            return {
                "status": "healthy",
                "component": "codegraph",
                "version": info.version,
            }

        return {
            "status": "degraded",
            "component": "codegraph",
            "version": info.version,
            "diagnostics": {
                "status_exit": result.returncode,
                "stderr": result.stderr[:200],
            },
        }
