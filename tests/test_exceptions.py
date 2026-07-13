"""Tests for domain exceptions (RED phase — classes don't exist yet).

Spec: module-system §Error Cases
"""

import pytest


class TestApochErrorHierarchy:
    """Verify exception hierarchy for Apoch domain errors."""

    def test_apoch_error_is_exception_subclass(self):
        """ApochError extends Exception."""
        from apoch.core.exceptions import ApochError

        assert issubclass(ApochError, Exception)

    def test_module_load_error_is_apoch_error(self):
        """ModuleLoadError extends ApochError."""
        from apoch.core.exceptions import ApochError, ModuleLoadError

        assert issubclass(ModuleLoadError, ApochError)

    def test_lifecycle_error_is_apoch_error(self):
        """LifecycleError extends ApochError."""
        from apoch.core.exceptions import ApochError, LifecycleError

        assert issubclass(LifecycleError, ApochError)

    def test_state_transition_error_is_apoch_error(self):
        """StateTransitionError extends ApochError."""
        from apoch.core.exceptions import ApochError, StateTransitionError

        assert issubclass(StateTransitionError, ApochError)

    def test_storage_error_is_apoch_error(self):
        """StorageError extends ApochError."""
        from apoch.core.exceptions import ApochError, StorageError

        assert issubclass(StorageError, ApochError)


class TestExceptionBehavior:
    """Verify each exception can be raised, caught, and carries a message."""

    def test_module_load_error_is_raiseable(self):
        """ModuleLoadError can be raised with a message and caught as its own type."""
        from apoch.core.exceptions import ModuleLoadError

        with pytest.raises(ModuleLoadError) as exc_info:
            raise ModuleLoadError("Cannot import module 'chronicle'")
        assert "Cannot import module" in str(exc_info.value)

    def test_module_load_error_is_caught_as_apoch_error(self):
        """ModuleLoadError is caught as ApochError (polymorphic catch)."""
        from apoch.core.exceptions import ApochError, ModuleLoadError

        with pytest.raises(ApochError):
            raise ModuleLoadError("test")

    def test_lifecycle_error_is_raiseable(self):
        """LifecycleError can be raised with a message."""
        from apoch.core.exceptions import LifecycleError

        with pytest.raises(LifecycleError) as exc_info:
            raise LifecycleError("start() called before init()")
        assert "start()" in str(exc_info.value)

    def test_state_transition_error_is_raiseable(self):
        """StateTransitionError can be raised with a message."""
        from apoch.core.exceptions import StateTransitionError

        with pytest.raises(StateTransitionError) as exc_info:
            raise StateTransitionError("Cannot transition from STOPPED to RUNNING")
        assert "transition" in str(exc_info.value).lower()

    def test_storage_error_is_raiseable(self):
        """StorageError can be raised with a message."""
        from apoch.core.exceptions import StorageError

        with pytest.raises(StorageError) as exc_info:
            raise StorageError("Disk full")
        assert "Disk full" in str(exc_info.value)
