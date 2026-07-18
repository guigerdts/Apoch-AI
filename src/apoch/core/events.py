"""Simple publish/subscribe event bus for inter-module communication.

Spec: module-system §Architecture
Design: Architecture Decisions (#0 — Event Bus)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for an async event handler that accepts ``**kwargs``.
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventTopics:
    """Canonical event topic constants.

    All event topic strings MUST reference these constants — never raw strings.
    """

    ENGINE_STARTED: str = "engine.started"
    ENGINE_STOPPING: str = "engine.stopping"
    MODULE_STARTED: str = "module.started"
    MODULE_STOPPED: str = "module.stopped"
    MODULE_FAILED: str = "module.failed"
    TOOL_INVOCATION: str = "tool.invocation"
    TOOL_COMPLETED: str = "tool.completed"
    TOOL_ERROR: str = "tool.error"


@dataclass(frozen=True)
class SystemEvent:
    """Immutable event passed through the EventBus.

    Fields:
        event_id:  ``uuid4.hex`` — unique identifier.
        topic:     From :class:`EventTopics` constants.
        source:    Module name, ``"engine"``, or ``"coordinator"``.
        timestamp: ISO 8601 UTC string.
        payload:   Context-specific data dict (immutable after construction).
    """

    event_id: str
    topic: str
    source: str
    timestamp: str
    payload: dict


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

    async def emit(self, event: str | SystemEvent, **kwargs: Any) -> None:
        """Emit an event, calling all registered handlers.

        Accepts either a plain *event* string (with **kwargs) or a
        :class:`SystemEvent` instance.  When called with a ``SystemEvent``,
        the topic is derived from ``event.topic`` and all ``event.payload``
        items are passed as kwargs alongside the ``event`` keyword.

        Exceptions from individual handlers are caught and logged so
        that one failing handler does not prevent others from running.
        """
        if isinstance(event, SystemEvent):
            await self._emit_system_event(event)
            return

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

    async def _emit_system_event(self, event: SystemEvent) -> None:
        """Emit a SystemEvent to handlers registered for ``event.topic``."""
        for handler in self._handlers.get(event.topic, []):
            try:
                await handler(event=event, **event.payload)
            except Exception as exc:
                logger.exception(
                    "Event handler '%s' failed for system event '%s': %s",
                    handler.__name__,
                    event.topic,
                    exc,
                )

    # ------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()


__all__ = [
    "EventBus",
    "EventHandler",
    "EventTopics",
    "SystemEvent",
]
