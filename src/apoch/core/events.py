"""Simple publish/subscribe event bus for inter-module communication.

Spec: module-system §Architecture
Design: Architecture Decisions (#0 — Event Bus)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for an async event handler that accepts ``**kwargs``.
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """Simple in-process publish/subscribe event bus.

    Provides a lightweight decoupling mechanism for core-to-module and
    module-to-module communication.  No external dependencies.

    Usage::

        bus = EventBus()

        @bus.on("module.started")
        async def handler(name: str) -> None:
            print(f"Module started: {name}")

        await bus.emit("module.started", name="chronicle")
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable[[EventHandler], EventHandler]:
        """Register a handler via decorator: ``@bus.on("event.name")``."""

        def decorator(handler: EventHandler) -> EventHandler:
            self._handlers[event].append(handler)
            return handler

        return decorator

    def subscribe(self, event: str, handler: EventHandler) -> None:
        """Register *handler* for the given *event*."""
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        """Remove a previously registered *handler* for *event*.

        No-op if the handler was not registered.
        """
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    async def emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event, calling all registered handlers.

        Exceptions from individual handlers are caught and logged so
        that one failing handler does not prevent others from running.
        """
        for handler in self._handlers.get(event, []):
            try:
                await handler(**kwargs)
            except Exception as exc:
                logger.exception(
                    "Event handler '%s' failed for event '%s': %s",
                    handler.__name__,
                    event,
                    exc,
                )

    # ------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()
