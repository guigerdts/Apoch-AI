"""OpenSpec Stack Component — adapter to the official Fission-AI CLI.

Apoch does **not** implement OpenSpec.  It acts as an adapter to the
official project at https://openspec.dev/ using its public CLI.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
Spec: core-stack
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

DESCRIPTOR = StackDescriptor(
    id="openspec",
    name="OpenSpec",
    kind="integrations",
    version="1.0.0",
    description="Spec-Driven Development for AI Assistants",
    entry_point="apoch.stack.components.openspec:OpenSpecComponent",
    install_command="npm install -g @fission-ai/openspec@latest",
    install_manager="npm",
    homepage="https://openspec.dev/",
    repository="https://github.com/fission-ai/OpenSpec",
    docs_url="https://openspec.dev/docs/",
    requires=("node>=20.19.0",),
    capabilities=("sdd", "specs", "changes"),
)


# ── Version regex ──────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)", re.MULTILINE)


def parse_openspec_version(output: str) -> str | None:
    """Extract a semantic version from *output*.

    Handles formats like ``"openspec 1.6.0"``, ``"v1.6.0"``, and
    ``"1.6.0"``.  Returns ``None`` when no version can be parsed.
    """
    if match := _VERSION_RE.search(output):
        return match.group(1)
    log.warning("Could not parse OpenSpec version from output: %r", output[:200])
    return None


# ── Component ──────────────────────────────────────────────────────────


class OpenSpecComponent(StackComponent):
    """Adapter for the official OpenSpec CLI.

    All lifecycle methods delegate to the official ``openspec`` npm
    package via :class:`CommandRunner`.  No internal reimplementation.
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        """Initialise with an optional custom *runner* (injectable for tests)."""
        self._runner = runner or RealRunner()

    @property
    def descriptor(self) -> StackDescriptor:
        """Return the static :data:`DESCRIPTOR` for OpenSpec."""
        return DESCRIPTOR

    # ── Lifecycle: detect ─────────────────────────────────────────────

    async def detect(self) -> ComponentInfo:
        """Locate the ``openspec`` binary and parse its version.

        Returns:
            ``ComponentInfo(installed=True, version=..., executable_path=...)``
            when the binary is found and its version parses correctly.
            ``ComponentInfo(installed=False)`` when the binary is not on
            ``$PATH`` or when the CLI invocation fails.
        """
        binary = shutil.which("openspec")
        if binary is None:
            log.info("OpenSpec binary not found on PATH")
            return ComponentInfo(installed=False)

        result = await self._runner.run(["openspec", "--version"])
        if result.returncode != 0:
            log.warning(
                "openspec --version exited with code %s: %s",
                result.returncode,
                result.stderr[:200],
            )
            return ComponentInfo(
                installed=False,
                metadata={"error": f"version check failed: {result.stderr[:200]}"},
            )

        version = parse_openspec_version(result.stdout)
        return ComponentInfo(
            installed=True,
            version=version,
            executable_path=Path(binary),
        )

    # ── Lifecycle: install ────────────────────────────────────────────

    async def install(self) -> OperationResult:
        """Install OpenSpec via npm.

        Prerequisites: Node.js >= 20.19.0.
        """
        log.info("OpenSpec install starting")
        cmd = ["npm", "install", "-g", "@fission-ai/openspec@latest"]
        log.info("Install command: %s", " ".join(cmd))

        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error(
                "OpenSpec install failed: %s",
                result.stderr[:500],
            )
            return OperationResult(
                success=False,
                component="openspec",
                message=f"Installation failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        # Confirm installation — binary must be present AND version parseable
        info = await self.detect()
        if info.installed and info.version is not None:
            log.info("OpenSpec installed successfully (version=%s)", info.version)
            return OperationResult(
                success=True,
                component="openspec",
                message=f"OpenSpec {info.version} installed",
            )

        if info.installed and info.version is None:
            log.warning(
                "OpenSpec binary found but version could not be parsed"
            )
            return OperationResult(
                success=False,
                component="openspec",
                message="OpenSpec binary found but version could not be parsed",
                details={"command": cmd},
            )

        log.warning("Install command succeeded but OpenSpec binary not found after install")
        return OperationResult(
            success=False,
            component="openspec",
            message="Install completed but OpenSpec binary not found on PATH",
            details={"command": cmd},
        )

    # ── Lifecycle: verify ─────────────────────────────────────────────

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Verify OpenSpec installation.

        Delegates to ``openspec doctor`` — the official read-only
        diagnostic.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="openspec",
                message="OpenSpec is not installed",
            )

        result = await self._runner.run(["openspec", "doctor"])
        if result.returncode != 0:
            log.warning(
                "OpenSpec verify — doctor failed (exit %s): %s",
                result.returncode,
                result.stderr[:200],
            )
            return OperationResult(
                success=False,
                component="openspec",
                message=f"openspec doctor failed (exit {result.returncode})",
                details={"doctor_exit": result.returncode},
            )

        return OperationResult(
            success=True,
            component="openspec",
            message=f"OpenSpec {info.version or ''} verified".strip(),
            details={"version": info.version},
        )

    # ── Lifecycle: activate / deactivate ──────────────────────────────

    async def activate(self) -> OperationResult:
        """Activate OpenSpec.

        Verifies that the binary is installed and operational.
        OpenSpec is a CLI binary — no session state to configure.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="openspec",
                message="OpenSpec is not installed — install it first",
            )
        return OperationResult(
            success=True,
            component="openspec",
            message=f"OpenSpec {info.version or ''} active".strip(),
        )

    async def deactivate(self) -> OperationResult:
        """Deactivate OpenSpec.

        No-op — OpenSpec is a CLI binary with no persistent session.
        """
        return OperationResult(
            success=True,
            component="openspec",
            message="OpenSpec deactivated",
        )

    # ── Lifecycle: uninstall ──────────────────────────────────────────

    async def uninstall(self) -> OperationResult:
        """Uninstall OpenSpec via npm."""
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=True,
                component="openspec",
                message="OpenSpec is not installed",
            )

        cmd = ["npm", "uninstall", "-g", "@fission-ai/openspec"]
        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error("OpenSpec uninstall failed: %s", result.stderr[:200])
            return OperationResult(
                success=False,
                component="openspec",
                message=f"Uninstall failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        log.info("OpenSpec uninstalled successfully")
        return OperationResult(
            success=True,
            component="openspec",
            message="OpenSpec uninstalled",
        )

    # ── Lifecycle: health ─────────────────────────────────────────────

    async def health(self) -> dict:
        """Return a health status dict for OpenSpec.

        Strategy (hybrid):
          1. Run ``openspec doctor --json`` and parse the JSON.
          2. If JSON is valid, use the ``"healthy"`` field as truth.
          3. If JSON is valid but has no ``healthy`` field, fall back
             to exit code.
          4. If ``--json`` is not supported or the JSON is invalid,
             fall back to exit code (``openspec doctor``).
          5. Never throw — degrade gracefully on parse errors.
        """
        info = await self.detect()
        if not info.installed:
            return {
                "status": "down",
                "component": "openspec",
                "version": None,
            }

        # Try JSON mode first
        result = await self._runner.run(["openspec", "doctor", "--json"])
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    healthy = data.get("root", {}).get("healthy")
                    if healthy is not None:
                        return {
                            "status": "healthy" if healthy else "degraded",
                            "component": "openspec",
                            "version": info.version,
                            "diagnostics": data,
                        }
                # Valid JSON but no "healthy" field — fallback to exit code
                log.warning(
                    "'openspec doctor --json' returned valid JSON without 'healthy' field; "
                    "falling back to exit code"
                )
            except json.JSONDecodeError:
                log.warning(
                    "Failed to parse 'openspec doctor --json'; falling back to exit code"
                )

        # Fallback: exit code only
        result = await self._runner.run(["openspec", "doctor"])
        if result.returncode == 0:
            return {
                "status": "healthy",
                "component": "openspec",
                "version": info.version,
            }

        return {
            "status": "degraded",
            "component": "openspec",
            "version": info.version,
            "diagnostics": {
                "doctor_exit": result.returncode,
                "stderr": result.stderr[:200],
            },
        }
