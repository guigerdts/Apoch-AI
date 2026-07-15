"""Stack-specific exception hierarchy.

All stack exceptions extend ``apoch.core.exceptions.ApochError`` so
callers can catch ``ApochError`` to handle any known error.
"""

from __future__ import annotations

from apoch.core.exceptions import ApochError


class StackError(ApochError):
    """Base exception for all Core Stack errors."""


class StackNotFoundError(StackError):
    """Raised when a component is not registered in the StackRegistry."""


class StackStateError(StackError):
    """Raised when an invalid state transition is attempted."""


class StackLockError(StackError):
    """Raised when the stack lock cannot be acquired or released."""


class StackInstallError(StackError):
    """Raised when a component installation fails."""


class StackUninstallError(StackError):
    """Raised when a component uninstallation fails."""


class StackVerifyError(StackError):
    """Raised when a component verification fails."""


class StackManifestError(StackError):
    """Raised when the stack manifest cannot be read or written."""


__all__ = [
    "StackError",
    "StackNotFoundError",
    "StackStateError",
    "StackLockError",
    "StackInstallError",
    "StackUninstallError",
    "StackVerifyError",
    "StackManifestError",
]
