"""Data types for the Vision observability module.

Spec: module-vision §Log Record Schema
Design: PR3C — Vision Module §Vision data types
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LogRecord:
    """A single structured log entry recorded by Vision.

    Fields:
        timestamp: When the log entry was created (UTC).
        level:     Severity — ``DEBUG``, ``INFO``, ``WARN``, ``ERROR``, ``FATAL``.
        message:   Human-readable log message.
        module:    Source module name, or ``None`` for Core/app messages.
        context:   Arbitrary structured key-value payload.
        pid:       Process ID that recorded the entry.
    """

    timestamp: datetime
    level: str
    message: str
    module: str | None
    pid: int
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemInfo:
    """Snapshot of process-level health and environment information.

    Fields:
        python_version:  Python interpreter version (e.g. ``"3.13.7"``).
        platform:        OS/platform identifier (e.g. ``"Linux-6.2.0..."``).
        pid:             Current process ID.
        uptime_seconds:  Seconds since ``VisionModule.start()`` was called.
        memory_rss_mb:   Resident set size in MB, or ``None`` if unavailable.
    """

    python_version: str
    platform: str
    pid: int
    uptime_seconds: float
    memory_rss_mb: float | None


__all__ = ["LogRecord", "SystemInfo"]
