"""Tests for Module ABC, ModuleMetadata, ModuleState (RED phase).

Spec: module-system §Lifecycle Contract, §Public Interfaces
"""

from abc import ABC
from enum import Enum

import pytest


class TestModuleMetadata:
    """ModuleMetadata dataclass with name, version, description, entry_point."""

    def test_metadata_has_name(self):
        """ModuleMetadata has a name field."""
        from apoch.core.module import ModuleMetadata

        meta = ModuleMetadata(
            name="chronicle",
            version="0.1.0",
            description="Activity recording",
            entry_point="apoch.modules.chronicle",
        )
        assert meta.name == "chronicle"

    def test_metadata_has_version(self):
        """ModuleMetadata has a version field."""
        from apoch.core.module import ModuleMetadata

        meta = ModuleMetadata(
            name="chronicle",
            version="0.1.0",
            description="Activity recording",
            entry_point="apoch.modules.chronicle",
        )
        assert meta.version == "0.1.0"

    def test_metadata_has_description(self):
        """ModuleMetadata has a description field."""
        from apoch.core.module import ModuleMetadata

        meta = ModuleMetadata(
            name="chronicle",
            version="0.1.0",
            description="Activity recording",
            entry_point="apoch.modules.chronicle",
        )
        assert meta.description == "Activity recording"

    def test_metadata_has_entry_point(self):
        """ModuleMetadata has an entry_point field."""
        from apoch.core.module import ModuleMetadata

        meta = ModuleMetadata(
            name="chronicle",
            version="0.1.0",
            description="Activity recording",
            entry_point="apoch.modules.chronicle",
        )
        assert meta.entry_point == "apoch.modules.chronicle"

    def test_metadata_is_dataclass(self):
        """ModuleMetadata is a dataclass with equality."""
        from apoch.core.module import ModuleMetadata

        a = ModuleMetadata("m", "1", "desc", "ep")
        b = ModuleMetadata("m", "1", "desc", "ep")
        assert a == b
        assert hash(a) == hash(b)


class TestModuleState:
    """ModuleState enum: LOADED, RUNNING, STOPPED, SHUTDOWN, FAILED."""

    def test_is_enum(self):
        """ModuleState is an Enum."""
        from apoch.core.module import ModuleState

        assert issubclass(ModuleState, Enum)

    def test_has_loaded(self):
        """ModuleState has LOADED member."""
        from apoch.core.module import ModuleState

        assert ModuleState.LOADED.value == "LOADED"

    def test_has_running(self):
        """ModuleState has RUNNING member."""
        from apoch.core.module import ModuleState

        assert ModuleState.RUNNING.value == "RUNNING"

    def test_has_stopped(self):
        """ModuleState has STOPPED member."""
        from apoch.core.module import ModuleState

        assert ModuleState.STOPPED.value == "STOPPED"

    def test_has_shutdown(self):
        """ModuleState has SHUTDOWN member."""
        from apoch.core.module import ModuleState

        assert ModuleState.SHUTDOWN.value == "SHUTDOWN"

    def test_has_failed(self):
        """ModuleState has FAILED member."""
        from apoch.core.module import ModuleState

        assert ModuleState.FAILED.value == "FAILED"


class TestModuleABC:
    """Module ABC enforces lifecycle methods via ABCMeta."""

    def test_module_is_abstract(self):
        """Module is an ABC with abstract methods."""
        from apoch.core.module import Module

        assert issubclass(Module, ABC)
        # Must have at least the three lifecycle abstractmethods
        assert "start" in Module.__abstractmethods__
        assert "stop" in Module.__abstractmethods__
        assert "shutdown" in Module.__abstractmethods__

    def test_module_cannot_be_instantiated_directly(self):
        """Module() raises TypeError because it has abstract methods."""
        from apoch.core.module import Module

        with pytest.raises(TypeError):
            Module({"key": "val"})

    def test_module_requires_start(self):
        """Subclass without start() cannot be instantiated."""
        from apoch.core.module import Module

        class IncompleteModule(Module):  # type: ignore[misc]
            pass

        with pytest.raises(TypeError):
            IncompleteModule({"key": "val"})

    def test_module_requires_stop(self):
        """Subclass without stop() cannot be instantiated."""
        from apoch.core.module import Module

        class IncompleteModule(Module):  # type: ignore[misc]
            async def start(self, context):  # noqa: ARG002
                pass

        with pytest.raises(TypeError):
            IncompleteModule({"key": "val"})

    def test_module_requires_shutdown(self):
        """Subclass without shutdown() cannot be instantiated."""
        from apoch.core.module import Module

        class IncompleteModule(Module):  # type: ignore[misc]
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

        with pytest.raises(TypeError):
            IncompleteModule({"key": "val"})

    def test_complete_module_can_be_instantiated(self):
        """Subclass with all abstract methods can be instantiated."""
        from apoch.core.module import Module, ModuleState

        class TestModule(Module):
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

            async def shutdown(self):
                pass

        instance = TestModule({"key": "val"})
        assert isinstance(instance, Module)
        assert instance._state is ModuleState.LOADED

    def test_module_constructor_accepts_config_dict(self):
        """Module.__init__ accepts a config dict."""
        from apoch.core.module import Module

        class TestModule(Module):
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

            async def shutdown(self):
                pass

        instance = TestModule({"log_level": "debug"})
        assert instance._config == {"log_level": "debug"}


class TestLifecycle:
    """Module lifecycle follows init→start→stop→shutdown."""

    @pytest.fixture
    def module(self):
        """Provide a concrete Module subclass for lifecycle tests."""
        from apoch.core.module import Module

        class LifecycleModule(Module):
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

            async def shutdown(self):
                pass

        return LifecycleModule({"key": "val"})

    @pytest.fixture
    def context(self):
        """Provide a Context instance."""
        from apoch.core.module import Context

        return Context()

    @pytest.mark.asyncio
    async def test_full_lifecycle_success(self, module, context):
        """init→start→stop→shutdown completes without error."""
        from apoch.core.module import ModuleState

        assert module._state is ModuleState.LOADED
        await module.start(context)
        assert module._state is ModuleState.RUNNING
        await module.stop()
        assert module._state is ModuleState.STOPPED
        await module.shutdown()
        assert module._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_double_start_raises_state_transition_error(self, module, context):
        """Starting an already-running module raises StateTransitionError."""
        from apoch.core.exceptions import StateTransitionError

        await module.start(context)
        with pytest.raises(StateTransitionError):
            await module.start(context)

    @pytest.mark.asyncio
    async def test_stop_before_start_raises_lifecycle_error(self, module):
        """Stopping before starting raises LifecycleError."""
        from apoch.core.exceptions import LifecycleError

        with pytest.raises(LifecycleError):
            await module.stop()

    @pytest.mark.asyncio
    async def test_shutdown_before_start_raises_lifecycle_error(self, module):
        """Shutting down before starting raises LifecycleError."""
        from apoch.core.exceptions import LifecycleError

        with pytest.raises(LifecycleError):
            await module.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_without_stop_raises_lifecycle_error(self, module, context):
        """Shutting down from RUNNING without stop raises LifecycleError."""
        from apoch.core.exceptions import LifecycleError

        await module.start(context)
        with pytest.raises(LifecycleError):
            await module.shutdown()

    @pytest.mark.asyncio
    async def test_stop_after_shutdown_raises_lifecycle_error(self, module, context):
        """Stopping a shut-down module raises LifecycleError."""
        from apoch.core.exceptions import LifecycleError

        await module.start(context)
        await module.stop()
        await module.shutdown()
        with pytest.raises(LifecycleError):
            await module.stop()

    @pytest.mark.asyncio
    async def test_start_after_shutdown_raises_lifecycle_error(self, module, context):
        """Starting a shut-down module raises LifecycleError."""
        from apoch.core.exceptions import LifecycleError

        await module.start(context)
        await module.stop()
        await module.shutdown()
        with pytest.raises(LifecycleError):
            await module.start(context)


class TestStateTransitions:
    """State machine validates transitions."""

    @pytest.fixture
    def module(self):
        """Provide a concrete Module subclass for state transition tests."""
        from apoch.core.module import Module

        class StateModule(Module):
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

            async def shutdown(self):
                pass

        return StateModule({"key": "val"})

    @pytest.fixture
    def context(self):
        """Provide a Context instance."""
        from apoch.core.module import Context

        return Context()

    @pytest.mark.asyncio
    async def test_loaded_to_running(self, module, context):
        """LOADED→RUNNING is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        assert module._state is ModuleState.RUNNING

    @pytest.mark.asyncio
    async def test_running_to_stopped(self, module, context):
        """RUNNING→STOPPED is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        module._transition(ModuleState.STOPPED)
        assert module._state is ModuleState.STOPPED

    @pytest.mark.asyncio
    async def test_stopped_to_shutdown(self, module, context):
        """STOPPED→SHUTDOWN is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        module._transition(ModuleState.STOPPED)
        module._transition(ModuleState.SHUTDOWN)
        assert module._state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_running_to_running_invalid(self, module, context):
        """RUNNING→RUNNING raises StateTransitionError."""
        from apoch.core.exceptions import StateTransitionError
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        with pytest.raises(StateTransitionError):
            module._transition(ModuleState.RUNNING)

    @pytest.mark.asyncio
    async def test_loaded_to_shutdown_invalid(self, module, context):
        """LOADED→SHUTDOWN raises StateTransitionError."""
        from apoch.core.exceptions import StateTransitionError
        from apoch.core.module import ModuleState

        with pytest.raises(StateTransitionError):
            module._transition(ModuleState.SHUTDOWN)


class TestFailedState:
    """FAILED state is reachable from any valid state."""

    @pytest.fixture
    def module(self):
        """Provide a concrete Module subclass for FAILED state tests."""
        from apoch.core.module import Module

        class FailModule(Module):
            async def start(self, context):  # noqa: ARG002
                pass

            async def stop(self):
                pass

            async def shutdown(self):
                pass

        return FailModule({"key": "val"})

    def test_transition_to_failed_from_loaded(self, module):
        """LOADED→FAILED is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.FAILED)
        assert module._state is ModuleState.FAILED

    def test_transition_to_failed_from_running(self, module):
        """RUNNING→FAILED is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        module._transition(ModuleState.FAILED)
        assert module._state is ModuleState.FAILED

    def test_transition_to_failed_from_stopped(self, module):
        """STOPPED→FAILED is a valid transition."""
        from apoch.core.module import ModuleState

        module._transition(ModuleState.RUNNING)
        module._transition(ModuleState.STOPPED)
        module._transition(ModuleState.FAILED)
        assert module._state is ModuleState.FAILED

    def test_failed_to_any_raises_state_transition_error(self, module):
        """FAILED→anything raises StateTransitionError."""
        from apoch.core.exceptions import StateTransitionError
        from apoch.core.module import ModuleState

        module._transition(ModuleState.FAILED)
        with pytest.raises(StateTransitionError):
            module._transition(ModuleState.RUNNING)
        with pytest.raises(StateTransitionError):
            module._transition(ModuleState.STOPPED)


class TestContext:
    """Context dataclass is a minimal execution context."""

    def test_context_is_dataclass(self):
        """Context is a dataclass and can be created."""
        from apoch.core.module import Context

        ctx = Context()
        assert ctx is not None
