"""Oracle — Recommendation Engine module.

Domain models, pure recommendation logic, and Module ABC lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apoch.modules.oracle.module import OracleModule

__all__: list[str] = ["OracleModule"]


def __getattr__(name: str) -> object:
    """Lazy-import OracleModule to avoid circular/early import issues."""
    if name == "OracleModule":
        from apoch.modules.oracle.module import OracleModule

        return OracleModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
