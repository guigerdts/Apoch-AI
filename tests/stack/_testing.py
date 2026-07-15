"""Shared test utilities for Stack component testing.

Defines two fakes — :class:`TrackerComponent` (records lifecycle calls
to a global log) and :class:`MockComponent` (silent no-op) — plus
helpers for building :class:`StackManager` instances pre-loaded with
those components.
"""

from __future__ import annotations

from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.manager import StackManager
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult

# ── Global call tracker ──────────────────────────────────────────────

_call_log: list[str] = []
"""Ordered call log shared across all components during a test.

Each entry has the form ``"{component}.{method}"`` (e.g.
``"comp-a.install"``).  Reset before each test via :func:`_reset_call_log`.
"""


def _reset_call_log() -> None:
    """Clear the global call log."""
    _call_log.clear()


# ── Tracker component (fake) ─────────────────────────────────────────


class TrackerComponent(StackComponent):
    """Fake component that records every lifecycle call to :data:`_call_log`.

    Enables precise order verification across multiple components during
    batch operations like ``install_all()`` and ``uninstall_all()``.
    """

    def __init__(self, descriptor: StackDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        return ComponentInfo(installed=True, version=self._descriptor.version)

    async def install(self) -> OperationResult:
        _call_log.append(f"{self._descriptor.name}.install")
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        _call_log.append(f"{self._descriptor.name}.uninstall")
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def activate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def deactivate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def health(self) -> dict:
        return {"status": "healthy"}


# ── Helpers ──────────────────────────────────────────────────────────


def make_descriptor(
    name: str,
    kind: str = "services",
    *,
    dependencies: tuple[str, ...] = (),
) -> StackDescriptor:
    """Create a ``StackDescriptor`` for a tracker component."""
    return StackDescriptor(
        name=name,
        kind=kind,
        version="1.0.0",
        description=f"Fake {name}",
        entry_point=f"test:{name}",
        dependencies=dependencies,
    )


def register_components(
    registry: StackRegistry,
    *names: str,
) -> dict[str, TrackerComponent]:
    """Register *names* and return ``{name: TrackerComponent}``.

    Each component gets an auto-generated descriptor with no dependencies.
    """
    instances: dict[str, TrackerComponent] = {}
    for name in names:
        desc = make_descriptor(name)
        registry.register(desc)
        instances[name] = TrackerComponent(desc)
    return instances


# ── Mock component (no-op) ────────────────────────────────────────────


class MockComponent(StackComponent):
    """Minimal mock component for testing.

    Unlike :class:`TrackerComponent`, ``MockComponent`` does **not**
    record calls to a global log.  Use it when the call-log tracking
    of ``TrackerComponent`` is unnecessary or would cause pollution.
    """

    def __init__(self, descriptor: StackDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        return ComponentInfo(installed=True, version=self._descriptor.version)

    async def install(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="verified")

    async def activate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="activated")

    async def deactivate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="deactivated")

    async def health(self) -> dict:
        return {"status": "healthy"}


# ── Helpers ──────────────────────────────────────────────────────────


def build_manager(*names: str) -> StackManager:
    """Create a ``StackManager`` pre-loaded with *names* as tracker components.

    Shortcut for single-test use.  For custom descriptors use
    ``register_components()`` directly.
    """
    registry = StackRegistry()
    instances = register_components(registry, *names)
    mgr = StackManager(registry)
    for name, instance in instances.items():
        mgr.register_instance(name, instance)
    return mgr
