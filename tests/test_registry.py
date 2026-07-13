"""RED tests for ModuleRegistry (Task 1.9).

Spec: module-system §Entry Point Discovery, §Enable/Disable
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apoch.core.exceptions import ModuleLoadError
from apoch.core.module import Context, Module, ModuleMetadata, ModuleState

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class _TestModule(Module):
    """A minimal concrete Module subclass for registry tests."""

    start_called = False
    stop_called = False
    shutdown_called = False

    async def start(self, context: Context) -> None:
        self.start_called = True

    async def stop(self) -> None:
        self.stop_called = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _FailingModule(Module):
    """Module that fails during start()."""

    async def start(self, context: Context) -> None:
        msg = "Intentional failure"
        raise RuntimeError(msg)

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


def _make_mock_ep(name: str, value: str, *, module_class=None, version=None, description=None):
    """Create a mock EntryPoint for testing."""
    from importlib.metadata import EntryPoint as _RealEntryPoint

    ep = MagicMock(spec=_RealEntryPoint)
    ep.name = name
    ep.value = value
    ep.group = "apoch.modules"

    if module_class is not None:
        ep.load.return_value = module_class
    else:
        ep.load.side_effect = ImportError(f"No module named {value}")

    if version is not None or description is not None:
        ep.dist = MagicMock()
        ep.dist.version = version or "0.0.0"
        ep.dist.metadata.get.return_value = description or ""
    else:
        ep.dist = None

    return ep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegistryConstructor:
    """ModuleRegistry constructor accepts optional config."""

    def test_constructor_defaults_to_empty_config(self):
        """ModuleRegistry() creates with empty config."""
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        assert reg._config == {}

    def test_constructor_accepts_config_dict(self):
        """ModuleRegistry(config) stores config."""
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry({"log_level": "debug", "modules": {}})
        assert reg._config["log_level"] == "debug"

    def test_loaded_is_empty_after_init(self):
        """No modules loaded after construction."""
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        assert reg.loaded == {}


class TestDiscover:
    """ModuleRegistry.discover() returns module metadata."""

    @patch("apoch.core.registry.entry_points")
    def test_discover_empty_when_no_entry_points(self, mock_eps):
        """discover() returns empty list when no entry points exist."""
        mock_eps.return_value = []
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert result == []

    @patch("apoch.core.registry.entry_points")
    def test_discover_returns_metadata_list(self, mock_eps):
        """discover() returns list of ModuleMetadata."""
        eps = [
            _make_mock_ep(
                "chronicle",
                "apoch.modules.chronicle.module:ChronicleModule",
                version="0.1.0",
                description="Activity recording",
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert len(result) == 1
        assert isinstance(result[0], ModuleMetadata)

    @patch("apoch.core.registry.entry_points")
    def test_discover_metadata_has_name(self, mock_eps):
        """discover() metadata includes module name."""
        eps = [
            _make_mock_ep("chronicle", "apoch.modules.chronicle.module:ChronicleModule"),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert result[0].name == "chronicle"

    @patch("apoch.core.registry.entry_points")
    def test_discover_metadata_has_version(self, mock_eps):
        """discover() metadata includes version from package."""
        eps = [
            _make_mock_ep(
                "chronicle",
                "apoch.modules.chronicle.module:ChronicleModule",
                version="0.1.0",
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert result[0].version == "0.1.0"

    @patch("apoch.core.registry.entry_points")
    def test_discover_metadata_default_version_when_no_dist(self, mock_eps):
        """discover() uses '0.0.0' when no distribution info."""
        ep = _make_mock_ep("chronicle", "apoch.modules.chronicle.module:ChronicleModule")
        ep.dist = None
        mock_eps.return_value = [ep]
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert result[0].version == "0.0.0"

    @patch("apoch.core.registry.entry_points")
    def test_discover_metadata_has_entry_point(self, mock_eps):
        """discover() metadata includes entry point string."""
        eps = [
            _make_mock_ep("chronicle", "apoch.modules.chronicle.module:ChronicleModule"),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert result[0].entry_point == "apoch.modules.chronicle.module:ChronicleModule"

    @patch("apoch.core.registry.entry_points")
    def test_discover_returns_multiple_metadata(self, mock_eps):
        """discover() returns metadata for all entry points."""
        eps = [
            _make_mock_ep("chronicle", "apoch.modules.chronicle.module:ChronicleModule"),
            _make_mock_ep("guardian", "apoch.modules.guardian.module:GuardianModule"),
            _make_mock_ep("vision", "apoch.modules.vision.module:VisionModule"),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        result = reg.discover()
        assert len(result) == 3
        names = {m.name for m in result}
        assert names == {"chronicle", "guardian", "vision"}


class TestLoad:
    """ModuleRegistry.load(name) loads and returns Module instances."""

    @patch("apoch.core.registry.entry_points")
    def test_load_returns_module_instance(self, mock_eps):
        """load(name) returns a Module instance."""
        eps = [
            _make_mock_ep("test_mod", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        module = reg.load("test_mod")
        assert isinstance(module, Module)
        assert isinstance(module, _TestModule)

    @patch("apoch.core.registry.entry_points")
    def test_load_raises_module_load_error_for_unknown_name(self, mock_eps):
        """load(name) raises ModuleLoadError for unknown module name."""
        mock_eps.return_value = []
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        with pytest.raises(ModuleLoadError):
            reg.load("nonexistent")

    @patch("apoch.core.registry.entry_points")
    def test_load_raises_module_load_error_for_broken_entry_point(self, mock_eps):
        """load(name) raises ModuleLoadError when entry point cannot be loaded."""
        eps = [
            _make_mock_ep(
                "broken",
                "nonexistent.module:Broken",
                module_class=None,
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        with pytest.raises(ModuleLoadError):
            reg.load("broken")

    @patch("apoch.core.registry.entry_points")
    def test_load_tracks_loaded_modules(self, mock_eps):
        """load(name) adds to loaded dict."""
        eps = [
            _make_mock_ep("test_mod", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        module = reg.load("test_mod")
        assert "test_mod" in reg.loaded
        assert reg.loaded["test_mod"] is module

    @patch("apoch.core.registry.entry_points")
    def test_load_returns_cached_module(self, mock_eps):
        """load(name) returns cached module on second call."""
        eps = [
            _make_mock_ep("test_mod", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        first = reg.load("test_mod")
        second = reg.load("test_mod")
        assert first is second

    @patch("apoch.core.registry.entry_points")
    def test_load_passes_module_config_from_config(self, mock_eps):
        """load(name) passes module-specific config to Module.__init__."""
        ep_calls = []

        class _ConfigCheckModule(Module):
            def __init__(self, config):
                nonlocal ep_calls
                ep_calls.append(config)
                super().__init__(config)

            async def start(self, context):
                pass
            async def stop(self):
                pass
            async def shutdown(self):
                pass

        eps = [
            _make_mock_ep(
                "test_mod", "tests.test_registry:_ConfigCheckModule",
                module_class=_ConfigCheckModule,
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry({
            "modules": {
                "test_mod": {"log_level": "debug"},
            },
        })
        reg.load("test_mod")
        assert len(ep_calls) == 1
        assert ep_calls[0] == {"log_level": "debug"}

    @patch("apoch.core.registry.entry_points")
    def test_load_passes_empty_config_when_no_module_config(self, mock_eps):
        """load(name) passes empty dict when no module config exists."""
        ep_calls = []

        class _EmptyConfigModule(Module):
            def __init__(self, config):
                nonlocal ep_calls
                ep_calls.append(config)
                super().__init__(config)

            async def start(self, context):
                pass
            async def stop(self):
                pass
            async def shutdown(self):
                pass

        eps = [
            _make_mock_ep(
                "test_mod", "tests.test_registry:_EmptyConfigModule",
                module_class=_EmptyConfigModule,
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry({"modules": {}})
        reg.load("test_mod")
        assert ep_calls[0] == {}


class TestStartAll:
    """ModuleRegistry.start_all(context) drives lifecycle."""

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_all_calls_start_on_loaded_modules(self, mock_eps, context):
        """start_all(context) calls start() on each loaded module."""
        eps = [
            _make_mock_ep("mod_a", "tests.test_registry:_TestModule", module_class=_TestModule),
            _make_mock_ep("mod_b", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        mod_a = reg.load("mod_a")
        mod_b = reg.load("mod_b")
        await reg.start_all(context)
        assert mod_a._state is ModuleState.RUNNING
        assert mod_b._state is ModuleState.RUNNING

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_start_all_continues_on_module_failure(self, mock_eps, context):
        """start_all() does not stop on a failing module."""
        eps = [
            _make_mock_ep(
                "failing", "tests.test_registry:_FailingModule",
                module_class=_FailingModule,
            ),
            _make_mock_ep(
                "ok", "tests.test_registry:_TestModule",
                module_class=_TestModule,
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        failing = reg.load("failing")
        ok = reg.load("ok")
        await reg.start_all(context)
        assert failing._state is ModuleState.FAILED
        assert ok._state is ModuleState.RUNNING


class TestStopAll:
    """ModuleRegistry.stop_all() reverses lifecycle."""

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_all_calls_stop_then_shutdown(self, mock_eps, context):
        """stop_all() calls stop() then shutdown() on loaded modules."""
        eps = [
            _make_mock_ep("mod_a", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        mod = reg.load("mod_a")
        await reg.start_all(context)
        assert mod._state is ModuleState.RUNNING
        await reg.stop_all()
        assert mod._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_all_reverse_order(self, mock_eps, context):
        """stop_all() processes modules in reverse init order."""
        stop_order = []
        shutdown_order = []

        class _OrderModuleA(Module):
            async def start(self, context): pass
            async def stop(self):
                stop_order.append("A")
            async def shutdown(self):
                shutdown_order.append("A")

        class _OrderModuleB(Module):
            async def start(self, context): pass
            async def stop(self):
                stop_order.append("B")
            async def shutdown(self):
                shutdown_order.append("B")

        eps = [
            _make_mock_ep("mod_a", "tests.test_registry:_OrderModuleA", module_class=_OrderModuleA),
            _make_mock_ep("mod_b", "tests.test_registry:_OrderModuleB", module_class=_OrderModuleB),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        reg.load("mod_a")
        reg.load("mod_b")
        await reg.start_all(context)
        await reg.stop_all()
        # Reverse init order: mod_b first, then mod_a
        assert stop_order == ["B", "A"]
        assert shutdown_order == ["B", "A"]

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_all_continues_on_module_failure(self, mock_eps, context):
        """stop_all() continues even if a module's stop() or shutdown() fails."""

        class _StopFailModule(Module):
            async def start(self, context): pass
            async def stop(self):
                msg = "stop failed"
                raise RuntimeError(msg)
            async def shutdown(self):
                msg = "shutdown failed"
                raise RuntimeError(msg)

        eps = [
            _make_mock_ep(
                "failing", "tests.test_registry:_StopFailModule",
                module_class=_StopFailModule,
            ),
            _make_mock_ep(
                "ok", "tests.test_registry:_TestModule",
                module_class=_TestModule,
            ),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        reg.load("failing")
        ok = reg.load("ok")
        await reg.start_all(context)
        await reg.stop_all()
        # The failing module should still allow the ok module to shut down
        assert ok._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_stop_all_no_loaded_modules_does_not_raise(self, mock_eps, context):
        """stop_all() on empty registry does not raise."""
        mock_eps.return_value = []
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        await reg.stop_all()  # should not raise


class TestLoadedProperty:
    """ModuleRegistry.loaded provides read-only view."""

    @patch("apoch.core.registry.entry_points")
    def test_loaded_returns_copy(self, mock_eps):
        """loaded property returns a copy, not internal dict."""
        eps = [
            _make_mock_ep("test_mod", "tests.test_registry:_TestModule", module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        reg.load("test_mod")
        view = reg.loaded
        # Modify the view — should not affect internal state
        view["evil"] = "hacked"
        assert "evil" not in reg.loaded


class TestIntegrationDiscovery:
    """End-to-end: full discover → load → start → stop cycle."""

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    @patch("apoch.core.registry.entry_points")
    async def test_discover_load_start_stop_cycle(self, mock_eps, context):
        """Full lifecycle round-trip with discover, load, start, stop."""
        eps = [
            _make_mock_ep("chronicle", "apoch.modules.chronicle.module:ChronicleModule",
                          version="0.1.0", description="Activity recording",
                          module_class=_TestModule),
            _make_mock_ep("guardian", "apoch.modules.guardian.module:GuardianModule",
                          version="0.2.0", description="Exception boundaries",
                          module_class=_TestModule),
        ]
        mock_eps.return_value = eps
        from apoch.core.registry import ModuleRegistry

        reg = ModuleRegistry()
        metadata = reg.discover()
        assert len(metadata) == 2
        assert metadata[0].name == "chronicle"
        assert metadata[1].name == "guardian"

        # Load only non-disabled
        chronicle = reg.load("chronicle")
        guardian = reg.load("guardian")
        assert chronicle._state is ModuleState.LOADED
        assert guardian._state is ModuleState.LOADED

        # Start all
        await reg.start_all(context)
        assert chronicle._state is ModuleState.RUNNING
        assert guardian._state is ModuleState.RUNNING

        # Stop all
        await reg.stop_all()
        assert chronicle._state is ModuleState.SHUTDOWN
        assert guardian._state is ModuleState.SHUTDOWN
