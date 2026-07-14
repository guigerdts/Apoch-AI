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


class OpenCodeConfigError(ApochError):
    """Raised when opencode.json cannot be read, written, or validated."""


class StorageError(ApochError):
    """Raised when a storage operation (read/write/delete) fails."""


class ToolExecutionError(ApochError):
    """Raised when an MCP tool dispatch or registration fails.

    Attributes:
        code:    Machine-readable error code (VALIDATION_ERROR, TOOL_NOT_FOUND,
                 HANDLER_NOT_FOUND, MODULE_ERROR, INTERNAL_ERROR).
        message: Human-readable description.
        details: Optional dict with additional context (e.g. traceback).
    """

    # Error codes
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    HANDLER_NOT_FOUND = "HANDLER_NOT_FOUND"
    MODULE_ERROR = "MODULE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}


__all__ = [
    "ApochError",
    "ConfigError",
    "ModuleLoadError",
    "LifecycleError",
    "StateTransitionError",
    "OpenCodeConfigError",
    "StorageError",
    "ToolExecutionError",
]
