"""Diagnostics data types for the Guardian exception-boundary module.

Spec: module-guardian §Guardian API (ModuleDiagnostics)
Design: PR3B — Guardian Module §Interfaces / Contracts
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDiagnostics:
    """Structured diagnostics captured when a module lifecycle call fails.

    Fields:
        module_name:       Fully-qualified class name of the module.
        current_state:     Module state after failure (typically ``FAILED``).
        last_error:        ``ExceptionType: message`` string.
        last_error_traceback: Full traceback from ``traceback.format_exc()``.
        fail_count:        Number of times this module has failed.
        last_failure_time: ISO-8601 timestamp of the most recent failure.
    """

    module_name: str
    current_state: str
    last_error: str | None
    last_error_traceback: str | None
    fail_count: int
    last_failure_time: str | None


__all__ = ["ModuleDiagnostics"]
