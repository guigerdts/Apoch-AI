"""Integration tests for Pulse auto-instrumentation (PR-1).

Tests the end-to-end flow: EventBus → PulseEventSubscriber → PulseModule → PulseStore.

Spec: pulse-auto-instrumentation §PulseEventSubscriber, §Auto-Exclusion, §Deduplication
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import pytest

from apoch.core.events import EventBus, EventTopics, SystemEvent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def pulse_store():
    """In-memory PulseStore for testing."""
    from apoch.modules.pulse.storage import PulseStore

    return PulseStore()


@pytest.fixture
def pulse_module(pulse_store):
    """Configured PulseModule pointing to the test PulseStore."""
    from apoch.modules.pulse.module import PulseModule

    mod = PulseModule(config={})
    mod._store = pulse_store
    return mod


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end: EventBus → Subscriber → PulseModule → PulseStore."""

    @pytest.mark.asyncio
    async def test_tool_completed_creates_work_unit(self, event_bus, pulse_module):
        """Emitting TOOL_COMPLETED creates a WorkUnit in PulseStore."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        await event_bus.emit(event)

        work_unit = pulse_module.get(event.event_id)
        assert work_unit is not None
        assert work_unit.id == event.event_id
        assert work_unit.model == "system"

    @pytest.mark.asyncio
    async def test_multiple_tool_events_create_multiple_work_units(self, event_bus, pulse_module):
        """Multiple tool events create multiple WorkUnits."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        for i in range(3):
            event = SystemEvent(
                event_id=uuid.uuid4().hex,
                topic=EventTopics.TOOL_COMPLETED,
                source="coordinator",
                timestamp=datetime.now(UTC).isoformat(),
                payload={"tool": f"tool_{i}"},
            )
            await event_bus.emit(event)

        assert pulse_module.count() == 3

    @pytest.mark.asyncio
    async def test_auto_exclusion_pulse_source(self, event_bus, pulse_module):
        """Events from source='pulse' are NOT recorded."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        # Emit a normal event first
        normal_event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        await event_bus.emit(normal_event)

        # Emit a pulse-sourced event that should be skipped
        pulse_event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="pulse",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_progress"},
        )
        await event_bus.emit(pulse_event)

        # Only the first event should be recorded
        assert pulse_module.count() == 1
        assert pulse_module.get(normal_event.event_id) is not None
        assert pulse_module.get(pulse_event.event_id) is None

    @pytest.mark.asyncio
    async def test_module_lifecycle_events_recorded(self, event_bus, pulse_module):
        """ENGINE_STARTED and ENGINE_STOPPING events are recorded."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        engine_started = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.ENGINE_STARTED,
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={},
        )
        await event_bus.emit(engine_started)

        engine_stopping = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.ENGINE_STOPPING,
            source="engine",
            timestamp=datetime.now(UTC).isoformat(),
            payload={},
        )
        await event_bus.emit(engine_stopping)

        assert pulse_module.get(engine_started.event_id) is not None
        assert pulse_module.get(engine_stopping.event_id) is not None

    @pytest.mark.asyncio
    async def test_subscriber_not_started_no_recording(self, event_bus, pulse_module):
        """Without start(), events are not recorded."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        PulseEventSubscriber(event_bus, pulse_module.record)
        # NOT starting the subscriber

        event = SystemEvent(
            event_id=uuid.uuid4().hex,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )
        await event_bus.emit(event)

        # No handlers registered, so nothing recorded
        assert pulse_module.count() == 0


class TestDedupIntegration:
    """Duplicate events handled gracefully."""

    @pytest.mark.asyncio
    async def test_same_event_twice_no_crash(self, event_bus, pulse_module, caplog):
        """Emitting the same SystemEvent twice does not crash."""
        from apoch.modules.pulse.events import PulseEventSubscriber

        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        event_id = uuid.uuid4().hex
        event = SystemEvent(
            event_id=event_id,
            topic=EventTopics.TOOL_COMPLETED,
            source="coordinator",
            timestamp=datetime.now(UTC).isoformat(),
            payload={"tool": "apoch_status"},
        )

        # First emit - should succeed
        await event_bus.emit(event)

        # Second emit - should not crash, log at DEBUG
        with caplog.at_level(logging.DEBUG):
            await event_bus.emit(event)

        # Only one WorkUnit should exist
        assert pulse_module.count() == 1


class TestExistingCoordinatorIntegration:
    """Integration with coordinator tool events."""

    @pytest.mark.asyncio
    async def test_coordinator_with_event_bus_no_crash(self, event_bus, pulse_module):
        """Coordinator with event_bus and subscriber does not crash."""
        from apoch.modules.pulse.events import PulseEventSubscriber
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        # Set up subscriber
        sub = PulseEventSubscriber(event_bus, pulse_module.record)
        sub.start()

        # Create coordinator with event_bus
        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        result = await coordinator.status()

        # At minimum, no crash. With empty registry, status returns error
        # which triggers TOOL_ERROR (not TOOL_COMPLETED), so subscriber
        # won't record it.
        assert isinstance(result, dict)
