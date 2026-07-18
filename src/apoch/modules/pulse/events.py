"""PulseEventSubscriber — transparent system event instrumentation.

Listens to EventBus events (TOOL_COMPLETED, ENGINE_STARTED, ENGINE_STOPPING)
and records them as Pulse measurements without modifying any existing module.

Spec: pulse-auto-instrumentation §PulseEventSubscriber, §Auto-Exclusion, §Deduplication
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apoch.core.events import EventBus, EventTopics, SystemEvent
from apoch.core.exceptions import StorageError
from apoch.modules.pulse.models import MeasurementInput

logger = logging.getLogger(__name__)

# Default measurement values for system events
_DEFAULT_SESSION_ID: str = "__system__"
_DEFAULT_MODEL: str = "system"
_DEFAULT_TOKENS_INPUT: int = 0
_DEFAULT_TOKENS_OUTPUT: int = 0
_DEFAULT_WALL_CLOCK_S: float = 0.0
_DEFAULT_LINES_ORIGINAL: int = 0
_DEFAULT_LINES_MODIFIED: int = 0


class PulseEventSubscriber:
    """Subscribes to EventBus and records system events as Pulse measurements.

    Uses a handler registry dict (never if/elif chains) keyed by
    :class:`EventTopics` constant.  Events from ``source="pulse"`` are
    skipped to prevent infinite feedback loops.

    Constructor:
        event_bus:  The :class:`EventBus` to subscribe to.
        record_fn:  Callable that accepts a :class:`MeasurementInput`.
                    Typically ``PulseModule.record()``.
    """

    def __init__(
        self,
        event_bus: EventBus,
        record_fn: Callable[[MeasurementInput], Any],
    ) -> None:
        self._event_bus = event_bus
        self._record_fn = record_fn
        self._handlers: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Register all handlers on the EventBus.

        Builds and subscribes the handler registry dict.
        """
        self._handlers = {
            EventTopics.TOOL_COMPLETED: self._handle_tool_completed,
            EventTopics.ENGINE_STARTED: self._handle_engine_started,
            EventTopics.ENGINE_STOPPING: self._handle_engine_stopping,
        }
        for topic, handler in self._handlers.items():
            self._event_bus.subscribe(topic, handler)

    # ------------------------------------------------------------------
    # Auto-exclusion guard (used by every handler)
    # ------------------------------------------------------------------

    def _should_skip(self, event: SystemEvent) -> bool:
        """Return True if *event* should be skipped (pulse source)."""
        return event.source == "pulse"

    # ------------------------------------------------------------------
    # Handlers (registry dict values — never if/elif)
    # ------------------------------------------------------------------

    async def _handle_tool_completed(self, event: SystemEvent, **payload: Any) -> None:  # noqa: ARG002
        """Handle a TOOL_COMPLETED event."""
        if self._should_skip(event):
            return
        self._record(
            MeasurementInput(
                session_id=_DEFAULT_SESSION_ID,
                work_unit_id=event.event_id,
                model=_DEFAULT_MODEL,
                tokens_input=_DEFAULT_TOKENS_INPUT,
                tokens_output=_DEFAULT_TOKENS_OUTPUT,
                wall_clock_s=_DEFAULT_WALL_CLOCK_S,
                lines_original=_DEFAULT_LINES_ORIGINAL,
                lines_modified=_DEFAULT_LINES_MODIFIED,
            )
        )

    async def _handle_engine_started(self, event: SystemEvent, **payload: Any) -> None:  # noqa: ARG002
        """Handle an ENGINE_STARTED event."""
        if self._should_skip(event):
            return
        self._record(
            MeasurementInput(
                session_id=_DEFAULT_SESSION_ID,
                work_unit_id=event.event_id,
                model=_DEFAULT_MODEL,
                tokens_input=_DEFAULT_TOKENS_INPUT,
                tokens_output=_DEFAULT_TOKENS_OUTPUT,
                wall_clock_s=_DEFAULT_WALL_CLOCK_S,
                lines_original=_DEFAULT_LINES_ORIGINAL,
                lines_modified=_DEFAULT_LINES_MODIFIED,
            )
        )

    async def _handle_engine_stopping(self, event: SystemEvent, **payload: Any) -> None:  # noqa: ARG002
        """Handle an ENGINE_STOPPING event."""
        if self._should_skip(event):
            return
        self._record(
            MeasurementInput(
                session_id=_DEFAULT_SESSION_ID,
                work_unit_id=event.event_id,
                model=_DEFAULT_MODEL,
                tokens_input=_DEFAULT_TOKENS_INPUT,
                tokens_output=_DEFAULT_TOKENS_OUTPUT,
                wall_clock_s=_DEFAULT_WALL_CLOCK_S,
                lines_original=_DEFAULT_LINES_ORIGINAL,
                lines_modified=_DEFAULT_LINES_MODIFIED,
            )
        )

    # ------------------------------------------------------------------
    # Recording (with dedup handling)
    # ------------------------------------------------------------------

    def _record(self, input: MeasurementInput) -> None:
        """Call the record function, catching StorageError for dedup."""
        try:
            self._record_fn(input)
        except StorageError:
            logger.debug(
                "Duplicate measurement '%s' — already recorded",
                input.work_unit_id,
            )
