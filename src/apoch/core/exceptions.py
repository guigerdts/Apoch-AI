"""Domain exceptions for the Apoch-AI module system.

All domain exceptions extend ``ApochError``, which extends ``Exception``,
so callers can catch ``ApochError`` to handle any known error without
catching bare ``Exception``.

Spec: module-system §Error Cases
"""


class ApochError(Exception):
    """Base exception for all Apoch-AI domain errors."""


class ModuleLoadError(ApochError):
    """Raised when a module entry point cannot be loaded or imported."""


class LifecycleError(ApochError):
    """Raised when a module lifecycle method is called out of order."""


class StateTransitionError(ApochError):
    """Raised when an invalid module state transition is attempted."""


class ConfigError(ApochError):
    """Raised when the configuration cannot be loaded or parsed."""


class StorageError(ApochError):
    """Raised when a storage operation (read/write/delete) fails."""


__all__ = [
    "ApochError",
    "ConfigError",
    "ModuleLoadError",
    "LifecycleError",
    "StateTransitionError",
    "StorageError",
]
