"""Data types for the Pulse productivity-intelligence module.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §Interfaces / Contracts
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class WorkUnit:
    """A recorded work unit with immutable productivity measurements.

    Immutable after creation — enforces the append-only constraint
    (Design §Append-only).  ``cost`` is ``None`` when the model does
    not have a configured price (R2 edge case).  ``completed_at`` is
    ``None`` for work units that are still in progress (R1 edge case).
    """

    id: str  # uuid4.hex
    session_id: str
    model: str
    tokens_input: int
    tokens_output: int
    wall_clock_s: float
    cost: Decimal | None = None
    created_at: str = ""  # ISO 8601 with µs, UTC
    completed_at: str | None = None  # ISO 8601; None if in-progress


@dataclass
class MeasurementInput:
    """Raw input accepted by Pulse to create a WorkUnit measurement.

    Mutable input data — validated and stored as an immutable
    :class:`WorkUnit`.  ``cost`` is ``None`` when the model has
    no configured price; Pulse does not invent a fallback.
    """

    session_id: str
    work_unit_id: str
    model: str
    tokens_input: int
    tokens_output: int
    wall_clock_s: float
    cost: Decimal | None = None


@dataclass
class TrendPoint:
    """A single data point in a productivity trend over a time period."""

    period_start: str  # ISO 8601
    period_end: str  # ISO 8601
    total_cost: Decimal
    total_tokens: int
    avg_cost_per_task: Decimal | None = None
    work_unit_count: int = 0


@dataclass
class WorkUnitFilter:
    """Query parameters for retrieving WorkUnit records.

    All fields are optional — only the specified criteria are applied.
    Results are ordered by *created_at* descending and capped at *limit*.
    """

    session_id: str | None = None
    model: str | None = None
    since: str | None = None  # ISO 8601
    until: str | None = None  # ISO 8601
    limit: int = 100


__all__ = [
    "MeasurementInput",
    "TrendPoint",
    "WorkUnit",
    "WorkUnitFilter",
]
