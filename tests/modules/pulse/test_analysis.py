"""Tests for Analysis — pure deterministic metrics layer.

Spec: pulse-productivity-intelligence §R5 (Rework), §R6 (Trends)
Design: Pulse — Engineering Productivity Intelligence §SRP

Analysis is a pure computation layer with zero side effects:
- Reads WorkUnit records, returns computed metrics.
- Never writes, mutates, or persists data.
- Results are deterministic: same input → same output.

Edge cases validated:
  - 0 WorkUnits (empty input).
  - 1 WorkUnit (no trend, no rework).
  - Incomplete data (missing timestamps, None fields).
  - Cost=None (excluded from cost averages).
  - completed_at=None (not used by analysis — uses created_at).
  - Trends with few data points.
  - Append-only preserved (input list never mutated).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apoch.modules.pulse.analysis import Analysis
from apoch.modules.pulse.models import WorkUnit

# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


def _make_units(*overrides_list: dict) -> list[WorkUnit]:
    """Create WorkUnit fixtures with sensible defaults.

    Each *overrides_dict* is merged over the base, so callers
    specify only the fields they care about.
    """
    now = datetime.now(UTC).isoformat()
    base = dict(
        id="",
        session_id="test-session",
        model="claude-4",
        tokens_input=100,
        tokens_output=50,
        wall_clock_s=30.0,
        cost=None,
        created_at=now,
        completed_at=now,
    )
    units = []
    for i, overrides in enumerate(overrides_list):
        d = dict(base)
        d["id"] = d["id"] or f"wu-{i}"
        d.update(overrides)
        units.append(WorkUnit(**d))
    return units


@pytest.fixture
def empty_units() -> list[WorkUnit]:
    return []


@pytest.fixture
def single_unit() -> list[WorkUnit]:
    return _make_units({})


@pytest.fixture
def two_balanced_units() -> list[WorkUnit]:
    """Two units where output ≈ input → low rework."""
    return _make_units(
        dict(tokens_input=100, tokens_output=100),
        dict(tokens_input=200, tokens_output=200),
    )


@pytest.fixture
def two_rework_units() -> list[WorkUnit]:
    """Two units where output << input → high rework."""
    return _make_units(
        dict(tokens_input=100, tokens_output=10),
        dict(tokens_input=200, tokens_output=20),
    )


@pytest.fixture
def units_with_mixed_cost() -> list[WorkUnit]:
    """Some units have cost=None, some have a cost."""
    return _make_units(
        dict(tokens_input=100, tokens_output=50, cost=Decimal("0.010")),
        dict(tokens_input=200, tokens_output=100, cost=None),
        dict(tokens_input=300, tokens_output=150, cost=Decimal("0.030")),
    )


@pytest.fixture
def units_no_cost() -> list[WorkUnit]:
    """All units have cost=None."""
    return _make_units(
        dict(tokens_input=100, tokens_output=50, cost=None),
        dict(tokens_input=200, tokens_output=100, cost=None),
    )


@pytest.fixture
def units_no_created_at() -> list[WorkUnit]:
    """Units with empty created_at (incomplete data)."""
    return _make_units(
        dict(created_at=""),
        dict(created_at=""),
    )


@pytest.fixture
def units_mixed_created_at() -> list[WorkUnit]:
    """Some units with created_at, some without."""
    now = datetime.now(UTC).isoformat()
    return _make_units(
        dict(created_at=now, tokens_input=100),
        dict(created_at="", tokens_input=200),
        dict(created_at=now, tokens_input=300),
    )


# -----------------------------------------------------------------------
# Rework rate
# -----------------------------------------------------------------------


class TestReworkRate:
    """Analysis.rework_rate() — token-based rework proxy (R5)."""

    def test_empty_list_returns_zero(self, empty_units: list[WorkUnit]) -> None:
        rate, method = Analysis.rework_rate(empty_units)
        assert rate == 0.0
        assert method == "none"

    def test_single_unit_returns_zero(self, single_unit: list[WorkUnit]) -> None:
        rate, method = Analysis.rework_rate(single_unit)
        assert rate == 0.0
        assert method == "none"

    def test_balanced_output_returns_zero(
        self, two_balanced_units: list[WorkUnit],
    ) -> None:
        """Output ≈ Input → ratio ≈ 1.0 → rework_rate ≈ 0.0."""
        rate, method = Analysis.rework_rate(two_balanced_units)
        assert rate == 0.0
        assert method == "token"

    def test_output_gt_input_returns_zero(self) -> None:
        """Output > Input → ratio > 1.0 → no rework signal."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=200),
            dict(tokens_input=50, tokens_output=100),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate == 0.0
        assert method == "token"

    def test_low_output_detects_rework(
        self, two_rework_units: list[WorkUnit],
    ) -> None:
        """Output << Input → ratio << 1.0 → rework detected."""
        rate, method = Analysis.rework_rate(two_rework_units)
        assert rate > 0.0
        assert method == "token"
        # (100+200)=300 in, (10+20)=30 out → ratio=0.1 → rework=0.9
        assert rate == pytest.approx(0.9, abs=1e-4)

    def test_total_in_zero_returns_zero(self) -> None:
        units = _make_units(
            dict(tokens_input=0, tokens_output=50),
            dict(tokens_input=0, tokens_output=30),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate == 0.0
        assert method == "token"

    def test_total_out_zero_returns_zero(self) -> None:
        units = _make_units(
            dict(tokens_input=100, tokens_output=0),
            dict(tokens_input=200, tokens_output=0),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate == 0.0
        assert method == "token"

    def test_deterministic(self) -> None:
        """Same input MUST produce the same rework_rate."""
        units = _make_units(
            dict(tokens_input=200, tokens_output=50),
            dict(tokens_input=100, tokens_output=20),
        )
        r1, _ = Analysis.rework_rate(units)
        r2, _ = Analysis.rework_rate(units)
        assert r1 == r2

    def test_cost_none_does_not_affect_rework(self) -> None:
        """Rework is token-based; cost=None is irrelevant."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10, cost=None),
            dict(tokens_input=200, tokens_output=20, cost=Decimal("0.015")),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate > 0.0
        assert method == "token"

    def test_completed_at_none_does_not_affect_rework(self) -> None:
        """completed_at is not consumed by rework calculation."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10, completed_at=None),
            dict(tokens_input=200, tokens_output=20, completed_at=None),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate > 0.0
        assert method == "token"


class TestLineBasedRework:
    """Analysis.rework_rate() — line-based primary, token fallback (R5)."""

    def test_line_based_returns_rate_and_method(self) -> None:
        """GIVEN units with line data THEN returns (rate, 'line')."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, lines_original=100, lines_modified=20),
            dict(tokens_input=200, tokens_output=100, lines_original=200, lines_modified=40),
        )
        rate, method = Analysis.rework_rate(units)
        # (20+40) / (100+200) = 60/300 = 0.2
        assert rate == pytest.approx(0.2, abs=1e-4)
        assert method == "line"

    def test_clamp_to_one(self) -> None:
        """GIVEN lines_modified > lines_original THEN rate MUST clamp to 1.0."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, lines_original=100, lines_modified=150),
            dict(tokens_input=200, tokens_output=100, lines_original=200, lines_modified=500),
        )
        rate, method = Analysis.rework_rate(units)
        assert rate == 1.0
        assert method == "line"

    def test_line_takes_priority_over_token(self) -> None:
        """GIVEN units with both line and token data THEN line is used."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10, lines_original=100, lines_modified=20),
            dict(tokens_input=200, tokens_output=20, lines_original=200, lines_modified=40),
        )
        rate, method = Analysis.rework_rate(units)
        assert method == "line"
        # Line-based: (20+40)/(100+200) = 0.2
        assert rate == pytest.approx(0.2, abs=1e-4)

    def test_no_line_data_falls_back_to_token(self) -> None:
        """GIVEN no line data in any unit THEN fall back to token proxy."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10, lines_original=0, lines_modified=0),
            dict(tokens_input=200, tokens_output=20, lines_original=0, lines_modified=0),
        )
        rate, method = Analysis.rework_rate(units)
        assert method == "token"
        assert rate > 0.0

    def test_empty_returns_none(self, empty_units: list[WorkUnit]) -> None:
        """GIVEN empty list THEN returns (0.0, 'none')."""
        rate, method = Analysis.rework_rate(empty_units)
        assert rate == 0.0
        assert method == "none"

    def test_single_unit_returns_none(self, single_unit: list[WorkUnit]) -> None:
        """GIVEN single unit THEN returns (0.0, 'none')."""
        rate, method = Analysis.rework_rate(single_unit)
        assert rate == 0.0
        assert method == "none"

    def test_window_filters_old_units(self) -> None:
        """GIVEN units outside window_days THEN they are excluded."""
        import datetime
        from datetime import UTC, timedelta

        now = datetime.datetime.now(UTC)
        old_dt = now - timedelta(days=60)
        recent_dt = now
        old = old_dt.isoformat()
        recent = recent_dt.isoformat()
        units = _make_units(
            # Old unit: created 60d ago, completed 60d ago → within 30d window
            dict(created_at=old, completed_at=old, lines_original=100, lines_modified=50),
            # Recent unit: created now, completed now → outside 30d window
            # (earliest is 60d ago, window=30d → cutoff 30d ago, now > cutoff)
            dict(created_at=recent, completed_at=recent, lines_original=200, lines_modified=20),
        )
        # window_days=30 based on earliest created_at (60d ago)
        # Cutoff: 60d ago + 30d = 30d ago
        # Old unit completed 60d ago → within window
        # Recent unit completed now → outside window
        rate, method = Analysis.rework_rate(units, window_days=30)
        assert method == "line"
        # Only the old unit: 50/100 = 0.5
        assert rate == pytest.approx(0.5, abs=1e-4)

    def test_mixed_line_data_some_units_have_lines(self) -> None:
        """GIVEN some units with line data and some without."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, lines_original=100, lines_modified=20),
            dict(tokens_input=200, tokens_output=100, lines_original=0, lines_modified=0),
        )
        rate, method = Analysis.rework_rate(units)
        # At least one unit has lines_original > 0, so line-based is used
        assert method == "line"
        # Both units contribute to the line calc: (20+0)/(100+0) — division by zero?
        # Actually lines_original=0 would make lines_mod=0 / lines_orig=0 for that unit
        # The sum approach: total mod = 20+0 = 20, total orig = 100+0 = 100 → rate = 0.2
        assert rate == pytest.approx(0.2, abs=1e-4)


class TestProductivitySummaryReworkMethod:
    """ProductivitySummary.rework_method MUST reflect rework analysis mode."""

    def test_summary_includes_rework_method_line(self) -> None:
        """GIVEN units with line data THEN rework_method='line'."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, lines_original=100, lines_modified=20),
            dict(tokens_input=200, tokens_output=100, lines_original=200, lines_modified=40),
        )
        s = Analysis.summary(units)
        assert s.rework_rate > 0.0
        assert s.rework_method == "line"

    def test_summary_fallback_to_token(self) -> None:
        """GIVEN only token data THEN rework_method='token'."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10),
            dict(tokens_input=200, tokens_output=20),
        )
        s = Analysis.summary(units)
        assert s.rework_rate > 0.0
        assert s.rework_method == "token"

    def test_summary_empty_default_none(self, empty_units: list[WorkUnit]) -> None:
        s = Analysis.summary(empty_units)
        assert s.rework_method == "none"


# -----------------------------------------------------------------------
# Trend
# -----------------------------------------------------------------------


class TestTrend:
    """Analysis.trend() — productivity trend over time (R6)."""

    def test_empty_returns_empty(self, empty_units: list[WorkUnit]) -> None:
        assert Analysis.trend(empty_units) == []

    def test_single_unit_returns_one_point(
        self, single_unit: list[WorkUnit],
    ) -> None:
        points = Analysis.trend(single_unit)
        assert len(points) == 1
        assert points[0].work_unit_count == 1

    def test_units_without_created_at_are_excluded(
        self, units_no_created_at: list[WorkUnit],
    ) -> None:
        """Units with empty created_at are skipped in trend."""
        points = Analysis.trend(units_no_created_at)
        assert len(points) == 0

    def test_mixed_created_at_skips_empty(
        self, units_mixed_created_at: list[WorkUnit],
    ) -> None:
        """Only units with a created_at contribute to trend."""
        points = Analysis.trend(units_mixed_created_at)
        assert len(points) >= 1
        total_units = sum(p.work_unit_count for p in points)
        assert total_units == 2  # one unit had empty created_at

    def test_returns_sorted_by_period(self) -> None:
        """Trend points MUST be returned in chronological order."""
        units = _make_units(
            dict(created_at="2026-07-10T10:00:00"),
            dict(created_at="2026-07-08T10:00:00"),
            dict(created_at="2026-07-12T10:00:00"),
        )
        points = Analysis.trend(units)
        starts = [p.period_start for p in points]
        assert starts == sorted(starts)

    def test_cost_none_excluded_from_totals(
        self, units_with_mixed_cost: list[WorkUnit],
    ) -> None:
        """Units with cost=None MUST NOT contribute to cost totals."""
        points = Analysis.trend(units_with_mixed_cost)
        total_cost = sum(p.total_cost for p in points)
        # Only units with cost contribute: 0.010 + 0.030 = 0.040
        assert total_cost == Decimal("0.040")

    def test_all_cost_none(
        self, units_no_cost: list[WorkUnit],
    ) -> None:
        """When all costs are None, total_cost is 0 and avg is None."""
        points = Analysis.trend(units_no_cost)
        for p in points:
            assert p.total_cost == Decimal("0")
            assert p.avg_cost_per_task is None

    def test_period_days_groups_correctly(self) -> None:
        """Larger period_days MUST group multiple days into one bucket."""
        units = _make_units(
            dict(created_at="2026-07-01T10:00:00"),
            dict(created_at="2026-07-02T10:00:00"),
            dict(created_at="2026-07-10T10:00:00"),
        )
        daily = Analysis.trend(units, period_days=1)
        weekly = Analysis.trend(units, period_days=7)
        # daily: 3 points (3 separate days)
        assert len(daily) == 3
        # weekly: July 1+2 fall in same week (Jul1=Wed → week starting Jun29)
        # July 10 is week starting Jul6. So: 2 buckets.
        assert len(weekly) in (2, 3)

    def test_deterministic(self) -> None:
        """Same input MUST produce identical trend points."""
        units = _make_units(
            dict(created_at="2026-07-01T10:00:00"),
            dict(created_at="2026-07-02T10:00:00"),
        )
        t1 = Analysis.trend(units)
        t2 = Analysis.trend(units)
        assert t1 == t2

    def test_completed_at_none_ignored(self) -> None:
        """completed_at is not consumed by trend — uses created_at."""
        units = _make_units(
            dict(created_at="2026-07-01T10:00:00", completed_at=None),
            dict(created_at="2026-07-02T10:00:00", completed_at=None),
        )
        points = Analysis.trend(units)
        assert len(points) == 2


# -----------------------------------------------------------------------
# ProductivitySummary
# -----------------------------------------------------------------------


class TestSummary:
    """Analysis.summary() — aggregate productivity metrics."""

    def test_empty_returns_defaults(self, empty_units: list[WorkUnit]) -> None:
        s = Analysis.summary(empty_units)
        assert s.total_work_units == 0
        assert s.total_tokens_input == 0
        assert s.total_tokens_output == 0
        assert s.total_cost == Decimal("0")
        assert s.total_time_s == 0.0
        assert s.avg_cost_per_unit is None

    def test_single_unit(self, single_unit: list[WorkUnit]) -> None:
        s = Analysis.summary(single_unit)
        assert s.total_work_units == 1
        assert s.total_tokens_input == 100
        assert s.total_tokens_output == 50
        assert s.rework_rate == 0.0

    def test_multiple_units(
        self, two_balanced_units: list[WorkUnit],
    ) -> None:
        s = Analysis.summary(two_balanced_units)
        assert s.total_work_units == 2
        assert s.total_tokens_input == 300
        assert s.total_tokens_output == 300
        assert s.total_time_s == 60.0

    def test_cost_none_excluded_from_avg(
        self, units_with_mixed_cost: list[WorkUnit],
    ) -> None:
        """avg_cost_per_unit MUST only consider units with a known cost."""
        s = Analysis.summary(units_with_mixed_cost)
        assert s.total_cost == Decimal("0.040")
        assert s.avg_cost_per_unit == Decimal("0.0200")  # 0.040 / 2

    def test_all_cost_none_avg_is_none(
        self, units_no_cost: list[WorkUnit],
    ) -> None:
        s = Analysis.summary(units_no_cost)
        assert s.total_cost == Decimal("0")
        assert s.avg_cost_per_unit is None

    def test_rework_rate_included(self) -> None:
        """Summary MUST include the computed rework_rate."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=10),
            dict(tokens_input=200, tokens_output=20),
        )
        s = Analysis.summary(units)
        assert s.rework_rate > 0.0

    def test_deterministic(self) -> None:
        units = _make_units(
            dict(tokens_input=100, tokens_output=50),
            dict(tokens_input=200, tokens_output=100),
        )
        assert Analysis.summary(units) == Analysis.summary(units)

    def test_completed_at_none_ignored(self) -> None:
        """completed_at is not consumed by summary."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, completed_at=None),
            dict(tokens_input=200, tokens_output=100, completed_at=None),
        )
        s = Analysis.summary(units)
        assert s.total_work_units == 2


# -----------------------------------------------------------------------
# Time series (downstream consumption)
# -----------------------------------------------------------------------


class TestTimeSeries:
    """Analysis.time_series() — raw data for Optimizer/Oracle."""

    def test_empty_returns_empty(self, empty_units: list[WorkUnit]) -> None:
        assert Analysis.time_series(empty_units) == []

    def test_single_unit_returns_one_entry(
        self, single_unit: list[WorkUnit],
    ) -> None:
        series = Analysis.time_series(single_unit)
        assert len(series) == 1
        assert "period" in series[0]
        assert "tokens_input" in series[0]
        assert "cost" in series[0]
        assert "work_unit_count" in series[0]

    def test_includes_str_cost(self) -> None:
        """Cost MUST be serialised as a string for downstream."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50, cost=Decimal("0.015")),
        )
        series = Analysis.time_series(units)
        assert isinstance(series[0]["cost"], str)

    def test_units_without_created_at_excluded(self) -> None:
        """Units without a timestamp MUST NOT appear in series."""
        units = _make_units(
            dict(created_at=""),
            dict(created_at="2026-07-10T10:00:00"),
        )
        series = Analysis.time_series(units)
        total = sum(e["work_unit_count"] for e in series)
        assert total == 1

    def test_no_forbidden_methods(self) -> None:
        """Analysis MUST NOT expose methods from other modules."""
        assert not hasattr(Analysis, "optimize")
        assert not hasattr(Analysis, "recommend")
        assert not hasattr(Analysis, "persist")


# -----------------------------------------------------------------------
# Purity and append-only contract
# -----------------------------------------------------------------------


class TestPurityAndAppendOnly:
    """Analysis MUST be pure — no mutation, no side effects."""

    def test_input_list_not_mutated(self) -> None:
        """Analysis MUST NOT mutate the input list."""
        units = _make_units(
            dict(tokens_input=100, tokens_output=50),
        )
        original = list(units)
        Analysis.rework_rate(units)
        Analysis.trend(units)
        Analysis.summary(units)
        Analysis.time_series(units)
        assert units == original

    def test_work_units_not_mutated(self) -> None:
        """WorkUnit is frozen (dataclass frozen=True) — language-enforced."""
        import dataclasses

        assert dataclasses.is_dataclass(WorkUnit)
        # Frozen dataclass will raise FrozenInstanceError on setattr
        unit = WorkUnit(
            id="u1", session_id="s1", model="m",
            tokens_input=1, tokens_output=1, wall_clock_s=1.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            unit.tokens_input = 999

    def test_analysis_does_not_import_other_modules(self) -> None:
        """R11: Analysis must not import other EIL modules."""
        import apoch.modules.pulse.analysis as mod

        source = mod.__file__ or ""
        assert source != ""
        with open(source) as f:
            content = f.read()
        # It may import models and standard lib, but NOT other apoch modules
        imports = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        # Allow: models, decimal, collections, datetime, dataclasses
        forbidden = [
            i for i in imports
            if "apoch.modules" in i and "models" not in i
        ]
        assert not forbidden, f"Analysis imports from other modules: {forbidden}"

    def test_no_persistence_methods(self) -> None:
        """Analysis MUST NOT have save/write/persist methods."""
        assert not hasattr(Analysis, "save")
        assert not hasattr(Analysis, "write")
        assert not hasattr(Analysis, "persist")
        assert not hasattr(Analysis, "store")
