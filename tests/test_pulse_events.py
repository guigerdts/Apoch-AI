"""Tests for Phase 3: PulseEventSubscriber.

Spec: pulse-auto-instrumentation §PulseEventSubscriber, §Auto-Exclusion, §Deduplication
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from apoch.core.events import EventBus, EventTopics, SystemEvent
from apoch.core.exceptions import StorageError


@pytest.fixture
def event_bus():
    """Create a fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def mock_record_fn():
    """Create a mock record function that returns successfully."""
    return MagicMock(return_value=None)


def _make_event(
    topic: str,
    source: str = "coordinator",
    payload: dict | None = None,
) -> SystemEvent:
    """Helper to create a SystemEvent for testing."""
    return SystemEvent(
        event_id=uuid.uuid4().hex,
        topic=topic,
        source=source,
        timestamp=datetime.now(UTC).isoformat(),
        payload=payload or {},
    )


class TestPulseEventSubscriberConstructor:
    """PulseEventSubscriber can be instantiated."""

    def test_constructor_accepts_event_bus_and_record_fn(self, event_bus, mock_record_fn):
        """Constructor stores event_bus and record_fn."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        assert sub._event_bus is event_bus
        assert sub._record_fn is mock_record_fn

    def test_handlers_empty_before_start(self, event_bus, mock_record_fn):
        """Handlers dict is empty before start() is called."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        assert sub._handlers == {}


class TestPulseEventSubscriberStart:
    """Subscriber registers handlers on start()."""

    def test_start_subscribes_to_expected_topics(self, event_bus, mock_record_fn):
        """start() subscribes to TOOL_COMPLETED, ENGINE_STARTED, ENGINE_STOPPING."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        assert EventTopics.TOOL_COMPLETED in sub._handlers
        assert EventTopics.ENGINE_STARTED in sub._handlers
        assert EventTopics.ENGINE_STOPPING in sub._handlers
        assert len(sub._handlers) == 3

    def test_start_registers_on_event_bus(self, event_bus, mock_record_fn):
        """start() registers handlers on the EventBus via subscribe()."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        # Verify handlers are registered on the bus
        assert len(event_bus._handlers.get(EventTopics.TOOL_COMPLETED, [])) == 1
        assert len(event_bus._handlers.get(EventTopics.ENGINE_STARTED, [])) == 1
        assert len(event_bus._handlers.get(EventTopics.ENGINE_STOPPING, [])) == 1

    def test_handler_registry_dict_structure(self, event_bus, mock_record_fn):
        """Handlers are stored in a dict[str, Callable] keyed by EventTopics constant."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        assert isinstance(sub._handlers, dict)
        for topic in [
            EventTopics.TOOL_COMPLETED,
            EventTopics.ENGINE_STARTED,
            EventTopics.ENGINE_STOPPING,
        ]:
            assert topic in sub._handlers
            assert callable(sub._handlers[topic])


class TestPulseEventSubscriberHandlers:
    """Handlers transform events to MeasurementInput and call record_fn."""

    @pytest.mark.asyncio
    async def test_tool_completed_triggers_record(self, event_bus, mock_record_fn):
        """TOOL_COMPLETED event triggers record_fn call."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            payload={"tool": "apoch_status"},
        )
        await event_bus.emit(event)

        mock_record_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_engine_started_triggers_record(self, event_bus, mock_record_fn):
        """ENGINE_STARTED event triggers record_fn call."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.ENGINE_STARTED,
            source="engine",
        )
        await event_bus.emit(event)

        mock_record_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_engine_stopping_triggers_record(self, event_bus, mock_record_fn):
        """ENGINE_STOPPING event triggers record_fn call."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.ENGINE_STOPPING,
            source="engine",
        )
        await event_bus.emit(event)

        mock_record_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_receives_measurement_input(self, event_bus, mock_record_fn):
        """record_fn is called with a MeasurementInput."""
        from apoch.modules.pulse.events import PulseEventSubscriber
        from apoch.modules.pulse.models import MeasurementInput

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            payload={"tool": "apoch_status"},
        )
        await event_bus.emit(event)

        args, _ = mock_record_fn.call_args
        assert len(args) == 1
        assert isinstance(args[0], MeasurementInput)
        # Verify work_unit_id matches event_id
        assert args[0].work_unit_id == event.event_id


class TestUnhandledTopic:
    """Unhandled topics are silently ignored."""

    @pytest.mark.asyncio
    async def test_unhandled_topic_does_not_record(self, event_bus, mock_record_fn, caplog):
        """An event with unknown topic does not call record_fn."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.MODULE_STARTED,  # Not subscribed
            source="engine",
        )
        with caplog.at_level(logging.DEBUG):
            await event_bus.emit(event)

        mock_record_fn.assert_not_called()
        # No WARNING+ logs about unknown topic
        assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 0


class TestAutoExclusion:
    """Events with source='pulse' are skipped."""

    @pytest.mark.asyncio
    async def test_pulse_sourced_tool_completed_skipped(self, event_bus, mock_record_fn):
        """TOOL_COMPLETED from 'pulse' source is skipped."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="pulse",
            payload={"tool": "apoch_progress"},
        )
        await event_bus.emit(event)

        mock_record_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_pulse_sourced_engine_started_skipped(self, event_bus, mock_record_fn):
        """ENGINE_STARTED from 'pulse' source is skipped."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.ENGINE_STARTED,
            source="pulse",
        )
        await event_bus.emit(event)

        mock_record_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_pulse_source_not_skipped(self, event_bus, mock_record_fn):
        """Events from non-pulse sources are processed normally."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, mock_record_fn)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="chronicle",
            payload={"tool": "apoch_history"},
        )
        await event_bus.emit(event)

        mock_record_fn.assert_called_once()


class TestDedup:
    """Duplicate event_id is caught by StorageError and logged at DEBUG."""

    @pytest.mark.asyncio
    async def test_storage_error_caught_and_logged(self, event_bus, caplog):
        """StorageError from record_fn is caught and logged at DEBUG."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        def _failing_record(_input):
            raise StorageError("WorkUnit already exists")

        sub = PulseEventSubscriber(event_bus, _failing_record)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            payload={"tool": "apoch_status"},
        )
        with caplog.at_level(logging.DEBUG):
            await event_bus.emit(event)

        # Should not raise - error is caught
        # Check DEBUG log about duplicate
        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("already exists" in msg or "duplicate" in msg.lower() for msg in debug_msgs)

    @pytest.mark.asyncio
    async def test_storage_error_not_propagated(self, event_bus):
        """StorageError from record_fn is not propagated."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        def _failing_record(_input):
            raise StorageError("WorkUnit already exists")

        sub = PulseEventSubscriber(event_bus, _failing_record)
        sub.start()

        event = _make_event(
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            payload={"tool": "apoch_status"},
        )
        # Should complete without raising
        await event_bus.emit(event)
