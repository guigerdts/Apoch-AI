"""RED tests for Engine (Task 1.12).

Spec: module-system §Execution Flow
Design: Data Flow (Startup Flow, Shutdown Flow)

Core dependency rule:
  Engine may only import: core/*, config/*, stdlib
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apoch.core.events import EventBus
from apoch.core.module import Context, Module, ModuleState
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


class TestEngineConstructor:
    """Engine receives dependencies via constructor injection."""

    def test_constructor_accepts_registry(self):
        """Engine.__init__ accepts a ModuleRegistry."""
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        assert engine.registry is registry

    def test_constructor_accepts_config(self):
        """Engine.__init__ accepts a config dict."""
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry, config={"log_level": "debug"})
        assert engine._config["log_level"] == "debug"

    def test_constructor_accepts_event_bus(self):
        """Engine.__init__ accepts an EventBus."""
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        event_bus = EventBus()
        engine = Engine(registry=registry, event_bus=event_bus)
        assert engine.events is event_bus

    def test_constructor_creates_default_event_bus(self):
        """Engine.__init__ creates an EventBus when not provided."""
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        assert isinstance(engine.events, EventBus)

    def test_constructor_default_config(self):
        """Engine.__init__ defaults config to empty dict."""
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        assert engine._config == {}


class TestEngineStart:
    """Engine.start() bootstraps the module lifecycle."""

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_discover_and_load_modules(self, mock_eps, context):
        """Engine.start() discovers and loads modules."""
        eps = [
            MagicMock(name="chronicle", value="apoch.modules.chronicle.module:ChronicleModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        assert "chronicle" in registry.loaded

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_calls_registry_start_all(self, mock_eps, context):
        """Engine.start() calls registry.start_all()."""
        eps = [
            MagicMock(name="chronicle", value="apoch.modules.chronicle.module:ChronicleModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        mod = registry.loaded["chronicle"]
        assert mod._state is ModuleState.RUNNING

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_skips_disabled_modules(self, mock_eps, context):
        """Engine.start() skips modules disabled in config."""
        eps = [
            MagicMock(name="chronicle", value="apoch.modules.chronicle.module:ChronicleModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(
            registry=registry,
            config={"modules": {"chronicle": {"enabled": False}}},
        )
        await engine.start()
        assert "chronicle" not in registry.loaded

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_emits_engine_started_event(self, mock_eps, context):
        """Engine.start() emits 'engine.started' event."""
        mock_eps.return_value = []
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        event_bus = EventBus()
        results = []

        @event_bus.on("engine.started")
        async def handler():
            results.append("started")

        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()
        assert results == ["started"]

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_discover_no_modules(self, mock_eps, context):
        """Engine.start() handles zero discovered modules gracefully."""
        mock_eps.return_value = []
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()  # should not raise
        assert registry.loaded == {}


class TestEngineStop:
    """Engine.stop() gracefully shuts down modules."""

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_shuts_down_modules(self, mock_eps):
        """Engine.stop() calls registry.stop_all()."""
        eps = [
            MagicMock(name="chronicle", value="apoch.modules.chronicle.module:ChronicleModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        await engine.stop()
        mod = registry.loaded["chronicle"]
        assert mod._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_emits_events(self, mock_eps):
        """Engine.stop() emits 'engine.stopping' and 'engine.stopped' events."""
        mock_eps.return_value = []
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        event_bus = EventBus()
        results = []

        @event_bus.on("engine.stopping")
        async def on_stopping():
            results.append("stopping")

        @event_bus.on("engine.stopped")
        async def on_stopped():
            results.append("stopped")

        engine = Engine(registry=registry, event_bus=event_bus)
        await engine.start()
        await engine.stop()
        assert "stopping" in results
        assert "stopped" in results

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_without_start_does_not_raise(self, mock_eps):
        """Engine.stop() on non-started engine does not raise."""
        mock_eps.return_value = []
        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.stop()  # should not raise


class TestEngineStartStop:
    """Full start/stop lifecycle."""

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_full_start_stop_lifecycle(self, mock_eps):
        """Full start→stop cycle completes successfully."""
        eps = [
            MagicMock(name="chronicle", value="apoch.modules.chronicle.module:ChronicleModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "chronicle"
        eps[0].value = "apoch.modules.chronicle.module:ChronicleModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        assert "chronicle" in registry.loaded
        await engine.stop()
        assert registry.loaded["chronicle"]._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_only_loaded_modules_are_started(self, mock_eps):
        """Only modules that were loaded via load() are started."""
        eps = [
            MagicMock(name="mod_a", value="tests.test_engine:_GoodModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
            MagicMock(name="mod_b", value="tests.test_engine:_GoodModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "mod_a"
        eps[0].value = "tests.test_engine:_GoodModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        eps[1].name = "mod_b"
        eps[1].value = "tests.test_engine:_GoodModule"
        eps[1].group = "apoch.modules"
        eps[1].load.return_value = _GoodModule
        eps[1].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        # Disable mod_b
        engine = Engine(
            registry=registry,
            config={"modules": {"mod_b": {"enabled": False}}},
        )
        await engine.start()
        assert "mod_a" in registry.loaded
        assert "mod_b" not in registry.loaded

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_stop_multiple_modules(self, mock_eps):
        """Multiple modules start and stop correctly."""
        eps = [
            MagicMock(name="mod_a", value="tests.test_engine:_GoodModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
            MagicMock(name="mod_b", value="tests.test_engine:_GoodModule",
                      group="apoch.modules", spec=["name", "value", "group", "load", "dist"]),
        ]
        eps[0].name = "mod_a"
        eps[0].value = "tests.test_engine:_GoodModule"
        eps[0].group = "apoch.modules"
        eps[0].load.return_value = _GoodModule
        eps[0].dist = None
        eps[1].name = "mod_b"
        eps[1].value = "tests.test_engine:_GoodModule"
        eps[1].group = "apoch.modules"
        eps[1].load.return_value = _GoodModule
        eps[1].dist = None
        mock_eps.return_value = eps

        from apoch.core.engine import Engine

        registry = ModuleRegistry()
        engine = Engine(registry=registry)
        await engine.start()
        await engine.stop()
        assert registry.loaded["mod_a"]._state is ModuleState.SHUTDOWN
        assert registry.loaded["mod_b"]._state is ModuleState.SHUTDOWN
