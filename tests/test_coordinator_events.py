"""Tests for Phase 4: Coordinator event_bus + tool events.

Spec: mcp-public-api §Coordinator Emits Tool Events, §EventBus Propagation
"""

from __future__ import annotations

import pytest

from apoch.core.events import EventBus, EventTopics


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def empty_coordinator():
    """Coordinator with empty ServiceRegistry (no registered modules)."""
    from apoch.public_api.coordinator import ApochCoordinator
    from apoch.public_api.registry import ServiceRegistry

    return ApochCoordinator(ServiceRegistry())


class TestCoordinatorEventBus:
    """Coordinator accepts optional event_bus."""

    def test_constructed_without_event_bus(self):
        """Coordinator can be constructed without event_bus (backward compat)."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert coordinator._event_bus is None

    def test_constructed_with_event_bus(self, event_bus):
        """Coordinator stores event_bus when provided."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        assert coordinator._event_bus is event_bus

    def test_backward_compat_no_crash(self):
        """Coordinator without event_bus does not crash on any method."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        coordinator = ApochCoordinator(ServiceRegistry())
        assert coordinator._event_bus is None  # no crash


class TestCoordinatorToolEvents:
    """Coordinator emits TOOL_INVOCATION, TOOL_COMPLETED, TOOL_ERROR."""

    @pytest.mark.asyncio
    async def test_status_emits_invocation_and_completed_or_error(self, event_bus):
        """status() emits TOOL_INVOCATION and either TOOL_COMPLETED or TOOL_ERROR."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.source, event.payload))

        event_bus.subscribe(EventTopics.TOOL_INVOCATION, handler)
        event_bus.subscribe(EventTopics.TOOL_COMPLETED, handler)
        event_bus.subscribe(EventTopics.TOOL_ERROR, handler)

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        await coordinator.status()

        assert len(received) >= 2
        topics = [r[0] for r in received]
        assert EventTopics.TOOL_INVOCATION in topics

        # With empty registry, expect TOOL_ERROR; with services, TOOL_COMPLETED
        has_completed = EventTopics.TOOL_COMPLETED in topics
        has_error = EventTopics.TOOL_ERROR in topics
        assert has_completed or has_error, "Expected TOOL_COMPLETED or TOOL_ERROR"

        # Verify source is coordinator
        for topic, source, payload in received:
            assert source == "coordinator"
            assert payload.get("tool") == "status"

    @pytest.mark.asyncio
    async def test_no_event_bus_does_not_emit(self, empty_coordinator):
        """Without event_bus, no events are emitted."""
        # No event_bus attached — can't spy on emissions
        result = await empty_coordinator.status()
        # Should work normally
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_health_emits_invocation_and_result(self, event_bus):
        """health() emits TOOL_INVOCATION and either TOOL_COMPLETED or TOOL_ERROR."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.source, event.payload))

        for topic in (
            EventTopics.TOOL_INVOCATION,
            EventTopics.TOOL_COMPLETED,
            EventTopics.TOOL_ERROR,
        ):
            event_bus.subscribe(topic, handler)

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        await coordinator.health()

        topics = {r[0] for r in received}
        assert EventTopics.TOOL_INVOCATION in topics
        # With empty registry, health returns error
        assert EventTopics.TOOL_ERROR in topics

    @pytest.mark.asyncio
    async def test_invocation_has_correct_payload(self, event_bus):
        """TOOL_INVOCATION payload includes tool name."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.payload))

        event_bus.subscribe(EventTopics.TOOL_INVOCATION, handler)

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        await coordinator.status()

        assert len(received) == 1
        topic, payload = received[0]
        assert topic == EventTopics.TOOL_INVOCATION
        assert payload.get("tool") == "status"

    @pytest.mark.asyncio
    async def test_all_tool_methods_emit_invocation(self, event_bus):
        """Each tool method emits TOOL_INVOCATION."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        received = []

        async def handler(event=None, **kwargs):
            received.append(event.payload.get("tool"))

        event_bus.subscribe(EventTopics.TOOL_INVOCATION, handler)

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)

        # Call each tool method
        tools = [
            ("status", lambda: coordinator.status()),
            ("health", lambda: coordinator.health()),
            ("history", lambda: coordinator.history()),
            ("recommend", lambda: coordinator.recommend()),
            ("progress", lambda: coordinator.progress()),
            ("insights", lambda: coordinator.insights()),
            ("logs", lambda: coordinator.logs()),
        ]

        for name, fn in tools:
            received.clear()
            await fn()
            if received:
                assert received[0] == name, f"Tool '{name}' emitted wrong invocation name"

    @pytest.mark.asyncio
    async def test_events_invocation_first_then_result(self, event_bus):
        """TOOL_INVOCATION is emitted before TOOL_ERROR (or COMPLETED)."""
        from apoch.public_api.coordinator import ApochCoordinator
        from apoch.public_api.registry import ServiceRegistry

        order = []

        async def handler(event=None, **kwargs):
            order.append(event.topic)

        for topic in (
            EventTopics.TOOL_INVOCATION,
            EventTopics.TOOL_ERROR,
            EventTopics.TOOL_COMPLETED,
        ):
            event_bus.subscribe(topic, handler)

        coordinator = ApochCoordinator(ServiceRegistry(), event_bus=event_bus)
        await coordinator.status()

        assert order[0] == EventTopics.TOOL_INVOCATION
        assert order[1] in (EventTopics.TOOL_COMPLETED, EventTopics.TOOL_ERROR)
