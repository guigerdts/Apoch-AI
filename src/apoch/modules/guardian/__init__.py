"""Guardian module — exception boundaries and diagnostics for Apoch-AI.

Spec: module-guardian
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["GuardianModule"]


def __getattr__(name: str) -> Any:
    """Lazy-export ``GuardianModule`` to avoid circular imports at package level."""
    if name == "GuardianModule":
        from apoch.modules.guardian.module import GuardianModule  # noqa: PLC0415

        return GuardianModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
