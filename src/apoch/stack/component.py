"""Abstract base class for all stack components.

Every installable platform component (OpenSpec, Engram, Context7,
CodeGraph, etc.) implements ``StackComponent`` and registers its
descriptor via the ``apoch.stack.components`` entry-point group.

Design: Core Stack Installation & Lifecycle — StackComponent Interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from apoch.stack.descriptor import StackDescriptor
from apoch.stack.result import OperationResult


@dataclass(frozen=True)
class ComponentInfo:
    """Factual information about an installed component.

    Returned by :meth:`StackComponent.detect`.  Contains only what
    ``detect()`` observes on the local system — never inferred state
    or policy decisions.  State derivation is the :class:`StackManager`'s
    responsibility.

    Attributes:
        installed:         Whether the component is present on the system.
        version:           Installed version string, or ``None``.
        available_version: Latest available version string (for future
                           OUTDATED detection), or ``None``.
        executable_path:   Path to the component's executable, or ``None``.
        detected_at:       Timestamp when ``detect()`` was last called, or
                           ``None``.
        metadata:          Additional free-form observations.
    """

    installed: bool
    version: str | None = None
    available_version: str | None = None
    executable_path: Path | None = None
    detected_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class StackComponent(ABC):
    """Abstract interface for a stack-managed component.

    All lifecycle methods are async to allow for I/O-bound operations
    (network downloads, subprocess calls, file I/O).
    """

    @property
    @abstractmethod
    def descriptor(self) -> StackDescriptor:
        """Return the component's static descriptor."""
        ...

    @abstractmethod
    async def detect(self) -> ComponentInfo:
        """Inspect the local system and return factual installation info.

        ``detect()`` never infers state — it reports what it finds:
        whether the component is installed, which version, and where
        the executable lives.  The :class:`StackManager` uses this
        information together with the :class:`StackDescriptor` to
        derive the component's :class:`~apoch.stack.state.StackState`.

        Returns:
            A :class:`ComponentInfo` describing the local installation.
        """
        ...

    @abstractmethod
    async def install(self) -> OperationResult:
        """Install the component.

        Returns:
            An ``OperationResult`` indicating success or failure.
        """
        ...

    @abstractmethod
    async def uninstall(self) -> OperationResult:
        """Uninstall the component.

        Returns:
            An ``OperationResult`` indicating success or failure.
        """
        ...

    @abstractmethod
    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        """Verify the component is correctly installed.

        Args:
            skip_async: When ``True``, skip long-running asynchronous checks
                        (e.g. live API pings) and only verify local artifacts.

        Returns:
            An ``OperationResult`` with details of the verification.
        """
        ...

    @abstractmethod
    async def activate(self) -> OperationResult:
        """Activate the component after installation.

        Typically configures the component for the current session.

        Returns:
            An ``OperationResult`` indicating success or failure.
        """
        ...

    @abstractmethod
    async def deactivate(self) -> OperationResult:
        """Deactivate the component without uninstalling.

        Returns:
            An ``OperationResult`` indicating success or failure.
        """
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Run a functional check beyond existence and version.

        Unlike ``detect()`` (which asks "is it there?") and ``verify()``
        (which asks "is it correctly installed?"), ``health()`` asks
        **"does it actually work?"**.

        Example for ``OpenSpecComponent``: run ``openspec doctor`` or a
        real subcommand and report diagnostics.

        Returns:
            A dict with at least a ``"status"`` key (``"healthy"`` /
            ``"degraded"`` / ``"down"``) and optional diagnostic fields.
        """
        ...


__all__ = [
    "ComponentInfo",
    "StackComponent",
]
