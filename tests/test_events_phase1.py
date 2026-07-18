"""Tests for Phase 1: EventTopics, SystemEvent, EventBus overloading.

Spec: pulse-auto-instrumentation §SystemEvent, EventTopics
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest


class TestEventTopics:
    """EventTopics constants match spec values."""

    def test_constants_match_spec(self):
        """Each EventTopics constant matches its spec value."""
        from apoch.core.events import EventTopics

        assert EventTopics.ENGINE_STARTED == "engine.started"
        assert EventTopics.ENGINE_STOPPING == "engine.stopping"
        assert EventTopics.MODULE_STARTED == "module.started"
        assert EventTopics.MODULE_STOPPED == "module.stopped"
        assert EventTopics.MODULE_FAILED == "module.failed"
        assert EventTopics.TOOL_INVOCATION == "tool.invocation"
        assert EventTopics.TOOL_COMPLETED == "tool.completed"
        assert EventTopics.TOOL_ERROR == "tool.error"

    def test_all_constants_present(self):
        """All 8 expected constants are defined."""
        from apoch.core.events import EventTopics

        expected = {
            "ENGINE_STARTED",
            "ENGINE_STOPPING",
            "MODULE_STARTED",
            "MODULE_STOPPED",
            "MODULE_FAILED",
            "TOOL_INVOCATION",
            "TOOL_COMPLETED",
            "TOOL_ERROR",
        }
        actual = {k for k in dir(EventTopics) if not k.startswith("_")}
        assert actual == expected


class TestSystemEvent:
    """SystemEvent frozen dataclass."""

    def test_constructor(self):
        """SystemEvent can be constructed with all fields."""
        from apoch.core.events import SystemEvent

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic="engine.started",
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"key": "value"},
        )
        assert event.topic == "engine.started"
        assert event.source == "engine"
        assert event.payload == {"key": "value"}

    def test_is_frozen(self):
        """SystemEvent is immutable — modifying a field raises FrozenInstanceError."""
        from dataclasses import FrozenInstanceError

        from apoch.core.events import SystemEvent

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic="engine.started",
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={},
        )
        with pytest.raises(FrozenInstanceError):
            event.topic = "changed"

    def test_topic_matches_event_topics(self):
        """Event.topic matches EventTopics constants."""
        from apoch.core.events import EventTopics, SystemEvent

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        assert event.topic == EventTopics.TOOL_COMPLETED

    def test_event_id_is_uuid_hex(self):
        """event_id is a valid uuid4.hex string."""
        from apoch.core.events import SystemEvent

        eid = uuid.uuid4().hex
        event = SystemEvent(
            event_id=eid,
            topic="test",
            source="test",
            timestamp="2026-01-01T00:00:00",
            payload={},
        )
        assert event.event_id == eid
        assert len(event.event_id) == 32  # uuid4.hex is 32 chars
        assert isinstance(event.event_id, str)

    def test_timestamp_iso_format(self):
        """timestamp is ISO 8601 format."""
        from apoch.core.events import SystemEvent

        ts = datetime.now(UTC).isoformat()
        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic="test",
            source="test",
            timestamp=ts,
            payload={},
        )
        assert event.timestamp == ts


class TestEventBusSystemEventSupport:
    """EventBus.emit() accepts SystemEvent."""

    @pytest.mark.asyncio
    async def test_emit_system_event_dispatches_by_topic(self):
        """Emitting a SystemEvent dispatches to handlers registered for event.topic."""
        from apoch.core.events import EventBus, EventTopics, SystemEvent

        bus = EventBus()
        received = []

        async def handler(**kwargs):
            received.append(kwargs)

        bus.subscribe(EventTopics.TOOL_COMPLETED, handler)

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        await bus.emit(event)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_emit_system_event_passes_event_and_payload(self):
        """Handlers receive event object and payload kwargs."""
        from apoch.core.events import EventBus, EventTopics, SystemEvent

        bus = EventBus()
        received_event = None
        received_kwargs = None

        async def handler(event=None, **kwargs):
            nonlocal received_event, received_kwargs
            received_event = event
            received_kwargs = kwargs

        bus.subscribe(EventTopics.TOOL_COMPLETED, handler)

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        await bus.emit(event)
        assert received_event is event
        assert received_kwargs == {"tool": "apoch_status"}

    @pytest.mark.asyncio
    async def test_emit_str_still_works(self):
        """Emitting a str event still works (backward compat)."""
        from apoch.core.events import EventBus

        bus = EventBus()
        received = {}

        async def handler(**kwargs):
            nonlocal received
            received = kwargs

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", name="test")
        assert received == {"name": "test"}

    @pytest.mark.asyncio
    async def test_str_handler_signature_backward_compat(self):
        """Existing handlers that accept kwargs still work."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def handler(**kwargs):
            results.append(kwargs.get("msg", "no_msg"))

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", msg="hello")
        assert results == ["hello"]

    @pytest.mark.asyncio
    async def test_system_event_exception_isolation(self):
        """Exception in SystemEvent handler does not block other handlers."""
        from apoch.core.events import EventBus, EventTopics, SystemEvent

        bus = EventBus()
        results = []

        async def failing_handler(**kwargs):
            msg = "boom"
            raise RuntimeError(msg)

        async def good_handler(**kwargs):
            results.append("ok")

        bus.subscribe(EventTopics.ENGINE_STARTED, failing_handler)
        bus.subscribe(EventTopics.ENGINE_STARTED, good_handler)

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.ENGINE_STARTED,
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={},
        )
        await bus.emit(event)
        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_system_event_no_handlers_does_not_raise(self):
        """Emitting SystemEvent with no handlers does not raise."""
        from apoch.core.events import EventBus, EventTopics, SystemEvent

        bus = EventBus()
        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.MODULE_FAILED,
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={},
        )
        await bus.emit(event)  # should not raise
