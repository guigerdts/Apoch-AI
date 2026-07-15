"""OpenSpec Stack Component — adapter to the official Fission-AI CLI.

Apoch does **not** implement OpenSpec.  It acts as an adapter to the
official project at https://openspec.dev/ using its public CLI.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
Spec: core-stack
"""

from __future__ import annotations

import logging
import re

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

    async def detect(self) -> ComponentInfo:
        """Stub — detect replaces this in PR5.2 with real installation detection."""
        raise NotImplementedError("PR5.2")

    async def install(self) -> OperationResult:
        """Stub — install replaces this in PR5.2 with the npm install flow."""
        raise NotImplementedError("PR5.2")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Stub — verify replaces this in PR5.2 with version & health checks."""
        raise NotImplementedError("PR5.2")

    async def activate(self) -> OperationResult:
        """Stub — activate replaces this in PR5.2 with session config."""
        raise NotImplementedError("PR5.2")

    async def deactivate(self) -> OperationResult:
        """Stub — deactivate replaces this in PR5.2 with session teardown."""
        raise NotImplementedError("PR5.2")

    async def uninstall(self) -> OperationResult:
        """Stub — uninstall replaces this in PR5.2 with npm uninstall."""
        raise NotImplementedError("PR5.2")

    async def health(self) -> dict:
        """Stub — health replaces this in PR5.2 with a real diagnostic check."""
        raise NotImplementedError("PR5.2")
