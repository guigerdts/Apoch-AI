"""Engram Stack Component — adapter to the official Engram CLI.

Apoch does **not** implement Engram. It acts as an adapter to the
official project at https://github.com/Gentleman-Programming/engram
using its public CLI.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
Spec: core-stack
Reference Component: OpenSpec (PR5) — identical structure, adapter-specific logic only.
"""

from __future__ import annotations

import logging
import platform
import re
import shutil
from pathlib import Path

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.result import OperationResult
from apoch.stack.runner import CommandRunner, RealRunner

log = logging.getLogger(__name__)

# ── Descriptor ─────────────────────────────────────────────────────────

ENGRA_DESCRIPTOR = StackDescriptor(
    id="engram",
    name="Engram",
    kind="integrations",
    version="1.19.0",
    description="Persistent memory for AI coding agents",
    entry_point="apoch.stack.components.engram:EngramComponent",
    install_command="brew install gentleman-programming/tap/engram",
    install_manager="homebrew",
    homepage="https://github.com/Gentleman-Programming/engram",
    repository="https://github.com/Gentleman-Programming/engram",
    docs_url="https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md",
    requires=(),
    capabilities=("memory", "mcp", "search"),
)


# ── Version regex ──────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"(?:engram\s+)?v?(\d+\.\d+\.\d+)", re.MULTILINE)


def parse_engram_version(output: str) -> str | None:
    """Extract a semantic version from *output*.

    Handles formats like ``"engram 1.19.0"``, ``"v1.19.0"``, and
    ``"1.19.0"``.  Returns ``None`` when no version can be parsed.
    """
    if match := _VERSION_RE.search(output):
        return match.group(1)
    log.warning("Could not parse Engram version from output: %r", output[:200])
    return None


# ── Helpers ────────────────────────────────────────────────────────────


def _get_install_args() -> list[str]:
    """Return the platform-appropriate install args for Engram.

    Engram does not have a single universal install command.  The
    official docs recommend different methods per platform:
    https://github.com/Gentleman-Programming/engram/blob/main/docs/INSTALLATION.md
    """
    sys = platform.system()
    if sys == "Darwin":
        return ["brew", "install", "gentleman-programming/tap/engram"]
    if sys == "Linux":
        # Homebrew is the recommended path on Linux too when available
        return ["brew", "install", "gentleman-programming/tap/engram"]
    if sys == "Windows":
        return [
            "go",
            "install",
            "github.com/Gentleman-Programming/engram/cmd/engram@latest",
        ]
    # Fallback — show the brew command as representative
    return ["brew", "install", "gentleman-programming/tap/engram"]


def _get_uninstall_args(executable_path: Path | None) -> list[str] | None:
    """Return the platform-appropriate uninstall args, or ``None``."""
    if executable_path is None:
        return None

    # Detect Homebrew-managed binary path
    try:
        resolved = executable_path.resolve()
    except OSError:
        resolved = executable_path

    str_path = str(resolved)

    # Homebrew installs to /usr/local/bin/ or /opt/homebrew/bin/
    # Linuxbrew installs to /home/linuxbrew/.linuxbrew/bin/
    if (
        "/homebrew/" in str_path
        or ".linuxbrew/" in str_path
        or str_path.startswith("/usr/local/bin/engram")
    ):
        return ["brew", "uninstall", "engram"]

    sys = platform.system()
    if sys == "Windows":
        return [
            "go",
            "clean",
            "-i",
            "github.com/Gentleman-Programming/engram/cmd/engram",
        ]

    # Fallback: binary delete suggestion (logged, not executed by adapter)
    return None


# ── Component ──────────────────────────────────────────────────────────


class EngramComponent(StackComponent):
    """Adapter for the official Engram CLI.

    All lifecycle methods delegate to the official ``engram`` Go
    binary via :class:`CommandRunner`.  No internal reimplementation.
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        """Initialise with an optional custom *runner* (injectable for tests)."""
        self._runner = runner or RealRunner()

    @property
    def descriptor(self) -> StackDescriptor:
        """Return the static :data:`ENGRA_DESCRIPTOR` for Engram."""
        return ENGRA_DESCRIPTOR

    # ── Lifecycle: detect ─────────────────────────────────────────────

    async def detect(self) -> ComponentInfo:
        """Locate the ``engram`` binary and parse its version.

        Returns:
            ``ComponentInfo(installed=True, version=..., executable_path=...)``
            when the binary is found and its version parses correctly.
            ``ComponentInfo(installed=False)`` when the binary is not on
            ``$PATH`` or when the CLI invocation fails.
        """
        binary = shutil.which("engram")
        if binary is None:
            log.info("Engram binary not found on PATH")
            return ComponentInfo(installed=False)

        result = await self._runner.run(["engram", "version"])
        if result.returncode != 0:
            log.warning(
                "engram version exited with code %s: %s",
                result.returncode,
                result.stderr[:200],
            )
            return ComponentInfo(
                installed=False,
                metadata={"error": f"version check failed: {result.stderr[:200]}"},
            )

        version = parse_engram_version(result.stdout)
        return ComponentInfo(
            installed=True,
            version=version,
            executable_path=Path(binary),
        )

    # ── Lifecycle: install ────────────────────────────────────────────

    async def install(self) -> OperationResult:
        """Install Engram using the platform-appropriate method.

        No prerequisites — Engram is a static Go binary with zero
        runtime dependencies.
        """
        log.info("Engram install starting")
        cmd = _get_install_args()
        log.info("Install command for platform '%s': %s", platform.system(), cmd)

        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error(
                "Engram install failed: %s",
                result.stderr[:500],
            )
            return OperationResult(
                success=False,
                component="engram",
                message=f"Installation failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        # Confirm installation
        info = await self.detect()
        if info.installed:
            log.info("Engram installed successfully (version=%s)", info.version)
            return OperationResult(
                success=True,
                component="engram",
                message=f"Engram {info.version or ''} installed".strip(),
            )

        log.warning("Install command succeeded but Engram binary not found after install")
        return OperationResult(
            success=False,
            component="engram",
            message="Install completed but Engram binary not found on PATH",
            details={"command": cmd},
        )

    # ── Lifecycle: verify ─────────────────────────────────────────────

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Verify Engram installation.

        Three-phase check:
          1. Call ``detect()`` to observe the local installation.
          2. State derived by ``StackManager.verify()``.
          3. Run ``engram doctor`` — the official read-only diagnostic.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="engram",
                message="Engram is not installed",
            )

        # Run the official health diagnostic
        result = await self._runner.run(["engram", "doctor"])
        if result.returncode != 0:
            log.warning(
                "Engram verify — doctor failed (exit %s): %s",
                result.returncode,
                result.stderr[:200],
            )
            return OperationResult(
                success=False,
                component="engram",
                message=f"engram doctor failed (exit {result.returncode})",
                details={"doctor_exit": result.returncode},
            )

        return OperationResult(
            success=True,
            component="engram",
            message=f"Engram {info.version or ''} verified".strip(),
            details={"version": info.version},
        )

    # ── Lifecycle: activate / deactivate ──────────────────────────────

    async def activate(self) -> OperationResult:
        """Activate Engram.

        Verifies that the binary is installed and operational.
        Engram is a CLI binary — no session state to configure.
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="engram",
                message="Engram is not installed — install it first",
            )
        return OperationResult(
            success=True,
            component="engram",
            message=f"Engram {info.version or ''} active".strip(),
        )

    async def deactivate(self) -> OperationResult:
        """Deactivate Engram.

        No-op — Engram is a CLI binary with no persistent session.
        """
        return OperationResult(
            success=True,
            component="engram",
            message="Engram deactivated",
        )

    # ── Lifecycle: uninstall ──────────────────────────────────────────

    async def uninstall(self) -> OperationResult:
        """Uninstall Engram.

        Strategy depends on the install method (Homebrew vs. binary).
        """
        info = await self.detect()
        if not info.installed:
            return OperationResult(
                success=False,
                component="engram",
                message="Engram is not installed",
            )

        cmd = _get_uninstall_args(info.executable_path)

        if cmd is None:
            # Binary not managed by package manager — suggest manual removal
            log.info(
                "Engram uninstall: no package manager detected; "
                "binary at %s must be removed manually",
                info.executable_path,
            )
            return OperationResult(
                success=False,
                component="engram",
                message=(
                    f"Engram binary at {info.executable_path} was not installed via a "
                    f"package manager. Remove it manually and optionally delete ~/.engram/"
                ),
            )

        result = await self._runner.run(cmd)

        if result.returncode != 0:
            log.error("Engram uninstall failed: %s", result.stderr[:200])
            return OperationResult(
                success=False,
                component="engram",
                message=f"Uninstall failed (exit {result.returncode}): {result.stderr[:200]}",
                details={"command": cmd, "exit_code": result.returncode},
            )

        log.info("Engram uninstalled successfully")
        return OperationResult(
            success=True,
            component="engram",
            message="Engram uninstalled",
        )

    # ── Lifecycle: health ─────────────────────────────────────────────

    async def health(self) -> dict:
        """Return a health status dict for Engram.

        Uses the official ``engram doctor`` command for diagnostics.
        """
        info = await self.detect()
        if not info.installed:
            return {
                "status": "down",
                "component": "engram",
                "version": None,
            }

        result = await self._runner.run(["engram", "doctor"])
        if result.returncode == 0:
            return {
                "status": "healthy",
                "component": "engram",
                "version": info.version,
            }

        return {
            "status": "degraded",
            "component": "engram",
            "version": info.version,
            "diagnostics": {
                "doctor_exit": result.returncode,
                "stderr": result.stderr[:200],
            },
        }
