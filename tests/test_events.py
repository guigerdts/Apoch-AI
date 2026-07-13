"""RED tests for EventBus (Task 1.11).

Spec: module-system §Architecture
"""

from __future__ import annotations

import pytest


class TestEventBusConstructor:
    """EventBus can be instantiated."""

    def test_constructor_creates_empty_bus(self):
        """EventBus() creates an empty bus."""
        from apoch.core.events import EventBus

        bus = EventBus()
        assert bus is not None
        assert bus._handlers == {}


class TestSubscribeAndEmit:
    """Subscribe and emit round-trip."""

    @pytest.mark.asyncio
    async def test_subscribe_and_emit_single_handler(self):
        """Subscribed handler is called when event is emitted."""
        from apoch.core.events import EventBus

        bus = EventBus()
        called = False

        async def handler():
            nonlocal called
            called = True

        bus.subscribe("test.event", handler)
        await bus.emit("test.event")
        assert called

    @pytest.mark.asyncio
    async def test_emit_passes_kwargs_to_handler(self):
        """Emitted kwargs are passed to the handler."""
        from apoch.core.events import EventBus

        bus = EventBus()
        received = {}

        async def handler(**kwargs):
            nonlocal received
            received = kwargs

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", name="chronicle", status="running")
        assert received == {"name": "chronicle", "status": "running"}

    @pytest.mark.asyncio
    async def test_multiple_handlers_same_event(self):
        """All handlers for an event are called."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def handler_a():
            results.append("A")

        async def handler_b():
            results.append("B")

        bus.subscribe("test.event", handler_a)
        bus.subscribe("test.event", handler_b)
        await bus.emit("test.event")
        assert results == ["A", "B"]

    @pytest.mark.asyncio
    async def test_different_events_isolated(self):
        """Handlers for one event are not called for another."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def handler_a():
            results.append("A")

        async def handler_b():
            results.append("B")

        bus.subscribe("event.a", handler_a)
        bus.subscribe("event.b", handler_b)
        await bus.emit("event.a")
        assert results == ["A"]

    @pytest.mark.asyncio
    async def test_emit_no_handlers_does_not_raise(self):
        """Emitting an event with no handlers does not raise."""
        from apoch.core.events import EventBus

        bus = EventBus()
        await bus.emit("nonexistent.event")  # should not raise


class TestExceptionIsolation:
    """One failing handler does not prevent others from running."""

    @pytest.mark.asyncio
    async def test_failing_handler_does_not_block_others(self):
        """Exception in one handler doesn't stop other handlers."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def failing_handler():
            msg = "Intentional failure"
            raise RuntimeError(msg)

        async def good_handler():
            results.append("called")

        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", good_handler)
        await bus.emit("test.event")
        assert results == ["called"]


class TestUnsubscribe:
    """Unsubscribing removes a handler."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self):
        """Unsubscribed handler is no longer called."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def handler():
            results.append("called")

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        await bus.emit("test.event")
        assert results == []

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_handler_does_not_raise(self):
        """Unsubscribing a handler not registered does not raise."""
        from apoch.core.events import EventBus

        bus = EventBus()

        async def handler():
            pass

        bus.unsubscribe("test.event", handler)  # should not raise


class TestClear:
    """Clear removes all handlers."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_handlers(self):
        """After clear, no handlers are called."""
        from apoch.core.events import EventBus

        bus = EventBus()
        results = []

        async def handler():
            results.append("called")

        bus.subscribe("event.a", handler)
        bus.subscribe("event.b", handler)
        bus.clear()
        await bus.emit("event.a")
        await bus.emit("event.b")
        assert results == []


class TestDecoratorForm:
    """@bus.on(event) registers a handler."""

    @pytest.mark.asyncio
    async def test_on_decorator_registers_handler(self):
        """@bus.on('event') registers the decorated function."""
        from apoch.core.events import EventBus

        bus = EventBus()
        called = False

        @bus.on("test.event")
        async def handler():
            nonlocal called
            called = True

        await bus.emit("test.event")
        assert called

    @pytest.mark.asyncio
    async def test_on_decorator_with_kwargs(self):
        """@bus.on handler receives kwargs from emit."""
        from apoch.core.events import EventBus

        bus = EventBus()

        @bus.on("test.event")
        async def handler(msg: str):
            assert msg == "hello"

        await bus.emit("test.event", msg="hello")
