"""Pure deterministic analysis layer for the Pulse module.

Design: Pulse — Engineering Productivity Intelligence §SRP
Spec: pulse-productivity-intelligence §R5 (Rework), §R6 (Trends)

This module has **zero side effects**: it reads WorkUnit records and
returns computed metrics.  It never writes, mutates, or persists data.
Results are deterministic: same input → same output.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from apoch.modules.pulse.models import TrendPoint, WorkUnit


@dataclass
class ProductivitySummary:
    """Aggregate productivity metrics derived from a set of WorkUnits.

    All metrics are computed on-read and are deterministic.
    """

    total_work_units: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost: Decimal = Decimal("0")
    total_time_s: float = 0.0
    avg_tokens_per_unit: float = 0.0
    avg_cost_per_unit: Decimal | None = None
    avg_time_per_unit: float = 0.0
    rework_rate: float = 0.0  # v1: token-based proxy


class Analysis:
    """Pure, stateless analysis functions for Pulse.

    Every method is a classmethod that accepts ``list[WorkUnit]`` and
    returns computed results.  No mutation, no persistence, no I/O.

    R11: Analysis does not import or reference any other module.
    """

    @classmethod
    def rework_rate(cls, units: list[WorkUnit]) -> float:
        """Estimate rework rate from available measurement data.

        For v1, this is a token-based proxy: it compares the ratio of
        output tokens to input tokens across all work units.

        * ratio ≈ 1 → balanced generation, low rework
        * ratio << 1 → high rework (much input for little output)

        Returns 0.0 for empty or single-unit sets, or when the proxy
        does not apply.  Future enrichment with diff metadata will
        provide an accurate line-based calculation (R5).
        """
        if len(units) < 2:
            return 0.0

        total_in = sum(u.tokens_input for u in units)
        total_out = sum(u.tokens_output for u in units)

        if total_out == 0 or total_in == 0:
            return 0.0

        ratio = total_out / total_in
        # ratio of 1.0 means output ≈ input → low rework
        # ratio < 0.5 means high input for low output → possible rework
        if ratio >= 1.0:
            return 0.0
        return round(1.0 - ratio, 4)

    @classmethod
    def trend(
        cls,
        units: list[WorkUnit],
        period_days: int = 1,
    ) -> list[TrendPoint]:
        """Compute productivity trend grouped by time period.

        Work units are grouped into windows of *period_days* based on
        their ``created_at`` timestamp.  Each period becomes a
        :class:`TrendPoint` with totals and averages.

        Returns an empty list when no WorkUnits are provided.
        """
        if not units:
            return []

        # Group by period
        buckets: dict[str, list[WorkUnit]] = defaultdict(list)

        for u in units:
            if not u.created_at:
                continue
            period_key = _period_key(u.created_at, period_days)
            buckets[period_key].append(u)

        # Build trend points, sorted chronologically
        points: list[TrendPoint] = []
        for period_key in sorted(buckets):
            bucket = buckets[period_key]
            total_cost = sum((u.cost for u in bucket if u.cost is not None), Decimal("0"))
            total_tokens = sum(u.tokens_input + u.tokens_output for u in bucket)
            count = len(bucket)
            avg_cost = (
                round(total_cost / count, 4)
                if total_cost > 0 and count > 0
                else None
            )

            points.append(TrendPoint(
                period_start=_period_start(period_key),
                period_end=_period_end(period_key, period_days),
                total_cost=total_cost,
                total_tokens=total_tokens,
                avg_cost_per_task=avg_cost,
                work_unit_count=count,
            ))

        return points

    @classmethod
    def summary(cls, units: list[WorkUnit]) -> ProductivitySummary:
        """Compute aggregate productivity summary."""
        if not units:
            return ProductivitySummary()

        count = len(units)
        total_in = sum(u.tokens_input for u in units)
        total_out = sum(u.tokens_output for u in units)
        total_cost = sum((u.cost for u in units if u.cost is not None), Decimal("0"))
        total_time = sum(u.wall_clock_s for u in units)

        cost_units = [u for u in units if u.cost is not None]
        avg_cost = (
            round(total_cost / len(cost_units), 4)
            if cost_units
            else None
        )

        return ProductivitySummary(
            total_work_units=count,
            total_tokens_input=total_in,
            total_tokens_output=total_out,
            total_cost=total_cost,
            total_time_s=total_time,
            avg_tokens_per_unit=round((total_in + total_out) / count, 2),
            avg_cost_per_unit=avg_cost,
            avg_time_per_unit=round(total_time / count, 2),
            rework_rate=cls.rework_rate(units),
        )

    @classmethod
    def time_series(
        cls,
        units: list[WorkUnit],
        period_days: int = 1,
    ) -> list[dict]:
        """Return raw time-series data for downstream consumption.

        Each entry is a dict suitable for serialisation:
        ``{period, tokens_input, tokens_output, cost, count}``.

        Optimizer and Oracle consume this data externally — Analysis
        never calls them directly (R11).
        """
        points = cls.trend(units, period_days)
        return [
            {
                "period": p.period_start,
                "tokens_input": p.total_tokens,
                "cost": str(p.total_cost),
                "work_unit_count": p.work_unit_count,
            }
            for p in points
        ]


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _period_key(iso_timestamp: str, period_days: int) -> str:
    """Return a grouping key (``YYYY-MM-DD``) for the given period."""
    date_part = iso_timestamp[:10]  # "2026-07-14"
    if period_days <= 1:
        return date_part
    # Bucket into N-day windows
    from datetime import date, timedelta

    parts = date_part.split("-")
    d = date(int(parts[0]), int(parts[1]), int(parts[2]))
    epoch = date(2020, 1, 1)
    days_since_epoch = (d - epoch).days
    bucket = days_since_epoch // period_days
    bucket_start = epoch + timedelta(days=bucket * period_days)
    return bucket_start.isoformat()


def _period_start(period_key: str) -> str:
    """Normalise period key to ISO start."""
    if "T" in period_key:
        return period_key
    return f"{period_key}T00:00:00"


def _period_end(period_key: str, period_days: int) -> str:
    """Return ISO end timestamp for the period."""
    from datetime import date, timedelta

    if "T" in period_key:
        return period_key
    parts = period_key.split("-")
    start = date(int(parts[0]), int(parts[1]), int(parts[2]))
    end = start + timedelta(days=period_days)
    return end.isoformat()
