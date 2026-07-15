"""Structured operation result for stack commands.

Design: Core Stack Installation & Lifecycle — Structured Operation Results
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OperationResult:
    """Immutable result for a stack operation (install, uninstall, verify, etc.).

    Attributes:
        success:   ``True`` if the operation completed without error.
        component: Name of the component the operation targeted.
        message:   Human-readable summary.
        details:   Optional structured data (version, paths, errors, etc.).
    """

    success: bool
    component: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
