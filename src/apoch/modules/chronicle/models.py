"""Data types for the Chronicle activity-recording module.

Spec: module-chronicle §Public Interfaces
Design: PR3A — Chronicle Foundation §Interfaces / Contracts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActivityEvent:
    """A single recorded activity event.

    Immutable after creation.  *payload* is a free-form dict that
    survives round-trips through JSON serialisation — an optional
    ``"schema"`` key may be present for structured payloads.
    """

    id: str  # uuid4.hex
    timestamp: str  # ISO 8601 with µs, UTC
    type: str  # e.g. "lifecycle", "tool_invocation", "error"
    source: str  # module name
    severity: str  # "info" | "warning" | "error" | "fatal"
    payload: dict[str, Any]  # free-form; optional "schema" key


@dataclass
class EventFilter:
    """Query parameters for retrieving events.

    All fields are optional — only the specified criteria are applied.
    Results are ordered by *timestamp* descending and capped at *limit*.
    """

    type: str | None = None
    source: str | None = None
    severity: str | None = None
    since: str | None = None  # ISO 8601
    until: str | None = None  # ISO 8601
    limit: int = 100


@dataclass
class EventStats:
    """Aggregate statistics across recorded events."""

    total: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
