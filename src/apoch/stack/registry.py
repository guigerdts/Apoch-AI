"""Registry for discovering and tracking stack components.

Components register via the ``apoch.stack.components`` entry-point group
(``importlib.metadata``) and are stored in a thread-safe in-memory map.

Design: Core Stack Installation & Lifecycle — StackRegistry
Spec: core-stack §Registry
"""

from __future__ import annotations

import logging
import threading
from importlib.metadata import entry_points

from apoch.stack.descriptor import StackDescriptor
from apoch.stack.exceptions import StackNotFoundError

log = logging.getLogger(__name__)


class StackRegistry:
    """Thread-safe registry of ``StackDescriptor`` objects.

    Components are registered either programmatically (``register``) or
    discovered from installed packages via ``discover``.
    """

    def __init__(self) -> None:
        self._descriptors: dict[str, StackDescriptor] = {}
        self._lock = threading.Lock()

    def register(self, descriptor: StackDescriptor) -> None:
        """Register a component descriptor.

        Args:
            descriptor: The component descriptor to register.

        Raises:
            ValueError: If a component with the same name is already registered.
        """
        with self._lock:
            if descriptor.name in self._descriptors:
                msg = f"Component '{descriptor.name}' is already registered"
                log.warning("Duplicate registration", extra={"component": descriptor.name})
                raise ValueError(msg)
            self._descriptors[descriptor.name] = descriptor
            log.info("Component registered", extra={"component": descriptor.name})

    def get(self, name: str) -> StackDescriptor:
        """Look up a component descriptor by name.

        Args:
            name: The component name.

        Returns:
            The matching ``StackDescriptor``.

        Raises:
            StackNotFoundError: If no component is registered with that name.
        """
        with self._lock:
            try:
                return self._descriptors[name]
            except KeyError:
                msg = f"Stack component '{name}' is not registered"
                log.warning("Component not found in registry", extra={"component": name})
                raise StackNotFoundError(msg) from None

    def contains(self, name: str) -> bool:
        """Return ``True`` if a component with *name* is registered."""
        with self._lock:
            return name in self._descriptors

    def list(self) -> tuple[StackDescriptor, ...]:
        """Return a snapshot of all registered descriptors."""
        with self._lock:
            return tuple(self._descriptors.values())

    def discover(self, group: str = "apoch.stack.components") -> int:
        """Discover components via ``importlib.metadata`` entry points.

        Only registers components whose names are not already registered.
        Invalid entry points are logged and skipped — discovery never
        aborts due to a single failure.

        Args:
            group: The entry-point group to scan. Defaults to
                   ``"apoch.stack.components"``.

        Returns:
            The number of newly registered components.
        """
        eps = entry_points(group=group)
        count = 0
        with self._lock:
            for ep in eps:
                if ep.name in self._descriptors:
                    continue
                try:
                    cls = ep.load()
                    instance = cls()
                    self._descriptors[instance.descriptor.name] = instance.descriptor
                    count += 1
                    log.info(
                        "Component discovered via entry point",
                        extra={"component": ep.name, "group": group},
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "Invalid entry point skipped",
                        extra={"component": ep.name, "group": group, "error": str(exc)},
                    )
        return count
