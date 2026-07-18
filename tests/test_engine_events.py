"""Tests for Phase 2: Engine wires event_bus to Context and emits lifecycle events.

Spec: module-system §Engine Emits Module Lifecycle Events
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apoch.core.events import EventBus, EventTopics
from apoch.core.module import Context, Module
from apoch.core.registry import ModuleRegistry

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _GoodModule(Module):
    """Module that succeeds in all lifecycle methods."""

    async def start(self, context: Context) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _FailingStartModule(Module):
    """Module that fails during start()."""

    async def start(self, context: Context) -> None:
        msg = "start failed"
        raise RuntimeError(msg)

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEngineContextEventBus:
    """Engine passes event_bus to Context before start_all."""

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_context_gets_event_bus(self, mock_eps):
        """Context.event_bus is set to Engine's EventBus."""
        eps = [
            MagicMock(
                name="chronicle",
                value="apoch.modules.chronicle.module:ChronicleModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        event_bus = EventBus()
        registry = ModuleRegistry()
        engine = Engine(registry=registry, event_bus=event_bus)

        # Capture context from registry.start_all
        original_start_all = registry.start_all
        captured_context = None

        async def capture_start_all(context: Context) -> None:
            nonlocal captured_context
            captured_context = context
            await original_start_all(context)

        registry.start_all = capture_start_all

        await engine.start()
        assert captured_context is not None
        assert captured_context.event_bus is event_bus

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_context_event_bus_set_before_start_all(self, mock_eps):
        """event_bus is set on Context before start_all is called."""
        mock_eps.return_value = []

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        # With no modules, start_all does nothing but context should still exist
        assert engine._context is not None
        assert engine._context.event_bus is engine._events


class TestEngineModuleLifecycleEvents:
    """Engine emits MODULE_STARTED, MODULE_STOPPED, MODULE_FAILED."""

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_emits_module_started_for_running_modules(self, mock_eps):
        """After start_all, MODULE_STARTED is emitted for each RUNNING module."""
        eps = [
            MagicMock(
                name="mod_a",
                value="tests.test_engine_events:_GoodModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
        ]
        eps[0].name = "mod_a"
        eps[0].value = "tests.test_engine_events:_GoodModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        event_bus = EventBus()
        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.source, event.payload))

        event_bus.subscribe(EventTopics.MODULE_STARTED, handler)

        registry = ModuleRegistry()
        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()

        assert len(received) == 1
        topic, source, payload = received[0]
        assert topic == EventTopics.MODULE_STARTED
        assert source == "mod_a"
        assert isinstance(payload, dict)

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_emits_module_stopped_for_stopped_modules(self, mock_eps):
        """After stop_all, MODULE_STOPPED is emitted for each stopped module."""
        eps = [
            MagicMock(
                name="mod_a",
                value="tests.test_engine_events:_GoodModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
        ]
        eps[0].name = "mod_a"
        eps[0].value = "tests.test_engine_events:_GoodModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        event_bus = EventBus()
        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.source, event.payload))

        event_bus.subscribe(EventTopics.MODULE_STOPPED, handler)

        registry = ModuleRegistry()
        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()
        await engine.stop()

        assert len(received) == 1
        topic, source, payload = received[0]
        assert topic == EventTopics.MODULE_STOPPED
        assert source == "mod_a"

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_emits_module_failed_for_failed_modules(self, mock_eps):
        """After start_all, MODULE_FAILED is emitted for modules in FAILED state."""
        eps = [
            MagicMock(
                name="mod_a",
                value="tests.test_engine_events:_FailingStartModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
        ]
        eps[0].name = "mod_a"
        eps[0].value = "tests.test_engine_events:_FailingStartModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _FailingStartModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        event_bus = EventBus()
        received = []

        async def handler(event=None, **kwargs):
            received.append((event.topic, event.source, event.payload))

        event_bus.subscribe(EventTopics.MODULE_FAILED, handler)

        registry = ModuleRegistry()
        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()

        assert len(received) == 1
        topic, source, payload = received[0]
        assert topic == EventTopics.MODULE_FAILED
        assert source == "mod_a"

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_multiple_modules_all_events(self, mock_eps):
        """Multiple modules emit multiple lifecycle events."""
        eps = [
            MagicMock(
                name="mod_a",
                value="tests.test_engine_events:_GoodModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
            MagicMock(
                name="mod_b",
                value="tests.test_engine_events:_GoodModule",
                group="apoch.modules",
                spec=["name", "value", "group", "load", "dist"],
            ),
        ]
        for i, name in enumerate(["mod_a", "mod_b"]):
            eps[i].name = name
            eps[i].value = "tests.test_engine_events:_GoodModule"
            eps[i].group = "apoch.modules"
            eps[i].load.return_value = _GoodModule
            eps[i].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        event_bus = EventBus()
        started = []
        stopped = []

        async def on_started(event=None, **kwargs):
            started.append(event.source)

        async def on_stopped(event=None, **kwargs):
            stopped.append(event.source)

        event_bus.subscribe(EventTopics.MODULE_STARTED, on_started)
        event_bus.subscribe(EventTopics.MODULE_STOPPED, on_stopped)

        registry = ModuleRegistry()
        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()
        assert set(started) == {"mod_a", "mod_b"}

        await engine.stop()
        assert set(stopped) == {"mod_a", "mod_b"}
