"""Vision — structured logging and MCP-observable introspection.

Spec: module-vision
Design: PR3C — Vision Module
"""

from __future__ import annotations

from typing import Any

__all__ = ["VisionModule"]


def __getattr__(name: str) -> Any:
    """Lazy-export ``VisionModule`` to avoid circular imports."""
    if name == "VisionModule":
        from apoch.modules.vision.module import VisionModule  # noqa: PLC0415

        return VisionModule
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
