"""Context7 Stack Component — adapter to the official Context7 CLI.

Apoch does **not** implement Context7.  It acts as an adapter to the
official project at https://context7.com/ using its public CLI.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
Spec: context7-component
"""

from __future__ import annotations

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

CONTEXT7_DESCRIPTOR = StackDescriptor(
    id="context7",
    name="Context7",
    kind="integrations",
    version="0.5.4",
    description="Documentation intelligence for AI coding agents",
    entry_point="apoch.stack.components.context7:Context7Component",
    install_command="npm install -g ctx7",
    install_manager="npm",
    homepage="https://context7.com",
    repository="https://github.com/upstash/context7",
    docs_url="https://context7.com/docs",
    requires=("node>=18",),
    capabilities=("docs", "skills", "mcp"),
)


# ── Version regex ──────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"(?:ctx7\s+)?v?(\d+\.\d+\.\d+)", re.MULTILINE)


def _parse_version(output: str) -> str | None:
    """Extract a semantic version from *output*.

    Handles formats like ``"ctx7 0.5.4"``, ``"v0.5.4"``, and
    ``"0.5.4"``.  Returns ``None`` when no version can be parsed.
    """
    if match := _VERSION_RE.search(output):
        return match.group(1)
    log.warning("Could not parse Context7 version from output: %r", output[:200])
    return None


# ── Component ──────────────────────────────────────────────────────────


class Context7Component(StackComponent):
    """Adapter for the official Context7 CLI.

    All lifecycle methods delegate to the official ``ctx7`` npm
    package via :class:`CommandRunner`.  No internal reimplementation.
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        """Initialise with an optional custom *runner* (injectable for tests)."""
        self._runner = runner or RealRunner()

    @property
    def descriptor(self) -> StackDescriptor:
        """Return the static :data:`CONTEXT7_DESCRIPTOR` for Context7."""
        return CONTEXT7_DESCRIPTOR

    # ── Lifecycle: detect ─────────────────────────────────────────────

    async def detect(self) -> ComponentInfo:
        """Locate the ``ctx7`` binary and parse its version.

        Returns:
            ``ComponentInfo(installed=True, version=..., executable_path=...)``
            when the binary is found and its version parses correctly.
            ``ComponentInfo(installed=False)`` when the binary is not on
            ``$PATH`` or when the CLI invocation fails.
        """
        binary = shutil.which("ctx7")
        if binary is None:
            log.info("Context7 binary not found on PATH")
            return ComponentInfo(installed=False)

        result = await self._runner.run(["ctx7", "--version"])
        if result.returncode != 0:
            log.warning(
                "ctx7 --version exited with code %s: %s",
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
        """Install Context7 via npm.

        Prerequisites: Node.js >= 18.
        """
        log.info("Context7 install starting")
        cmd = ["npm", "install", "-g", "ctx7"]
        log.info("Install command: %s", " ".join(cmd))

        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error(
                "Context7 install failed: %s",
                result.stderr[:500],
            )
            return OperationResult(
                success=False,
                component="context7",
                message=f"Installation failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        # Confirm installation — binary must be present on PATH
        info = await self.detect()
        if info.installed:
            log.info("Context7 installed successfully (version=%s)", info.version)
            return OperationResult(
                success=True,
                component="context7",
                message=f"Context7 {info.version or ''} installed".strip(),
            )

        log.warning("Install command succeeded but Context7 binary not found after install")
        return OperationResult(
            success=False,
            component="context7",
            message="Install completed but Context7 binary not found on PATH",
            details={"command": cmd},
        )

    # ── Lifecycle: verify ─────────────────────────────────────────────

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Verify Context7 installation.

        Two-phase check:
          1. Call ``detect()`` to observe the local installation.
          2. Run ``ctx7 --help`` as a basic responsiveness check.

        Note: Context7 has no ``doctor`` command — ``--help`` is the
        closest functional check available.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="context7",
                message="Context7 is not installed",
            )

        # Basic responsiveness check (no doctor command available)
        result = await self._runner.run(["ctx7", "--help"])
        if result.returncode != 0:
            log.warning(
                "Context7 verify — --help failed (exit %s): %s",
                result.returncode,
                result.stderr[:200],
            )
            return OperationResult(
                success=False,
                component="context7",
                message=f"ctx7 --help failed (exit {result.returncode})",
                details={"help_exit": result.returncode},
            )

        return OperationResult(
            success=True,
            component="context7",
            message=f"Context7 {info.version or ''} verified".strip(),
            details={"version": info.version},
        )

    # ── Lifecycle: activate / deactivate ──────────────────────────────

    async def activate(self) -> OperationResult:
        """Activate Context7.

        Verifies that the binary is installed and operational.
        Context7 is a CLI binary — no session state to configure.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="context7",
                message="Context7 is not installed — install it first",
            )
        return OperationResult(
            success=True,
            component="context7",
            message=f"Context7 {info.version or ''} active".strip(),
        )

    async def deactivate(self) -> OperationResult:
        """Deactivate Context7.

        No-op — Context7 is a CLI binary with no persistent session.
        """
        return OperationResult(
            success=True,
            component="context7",
            message="Context7 deactivated",
        )

    # ── Lifecycle: uninstall ──────────────────────────────────────────

    async def uninstall(self) -> OperationResult:
        """Uninstall Context7 via npm.

        Follows npm semantics: uninstalling an already-absent package
        returns success (no-op, not an error).
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=True,
                component="context7",
                message="Context7 is not installed",
            )

        cmd = ["npm", "uninstall", "-g", "ctx7"]
        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error("Context7 uninstall failed: %s", result.stderr[:200])
            return OperationResult(
                success=False,
                component="context7",
                message=f"Uninstall failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        log.info("Context7 uninstalled successfully")
        return OperationResult(
            success=True,
            component="context7",
            message="Context7 uninstalled",
        )

    # ── Lifecycle: health ─────────────────────────────────────────────

    async def health(self) -> dict:
        """Return a health status dict for Context7.

        Strategy (detect-only — no doctor command available):
          1. Call ``self.detect()`` to check binary presence and version.
          2. Binary not found → ``"down"``.
          3. Binary found + version parseable → ``"healthy"``.
          4. Binary found but version unparseable → ``"degraded"``.
        """
        info = await self.detect()
        if not info.installed:
            return {
                "status": "down",
                "component": "context7",
                "version": None,
            }

        if info.version is not None:
            return {
                "status": "healthy",
                "component": "context7",
                "version": info.version,
            }

        return {
            "status": "degraded",
            "component": "context7",
            "version": None,
            "diagnostics": {
                "error": "version could not be parsed",
            },
        }
