"""Tests for ClockProvider, RealClock, and FakeClock.

Design: Core Stack Installation & Lifecycle — ClockProvider
All timestamps obtained through ClockProvider — never datetime.now() directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apoch.stack.clock import ClockProvider, FakeClock, RealClock


class TestClockProvider:
    """ClockProvider is abstract and cannot be instantiated."""

    def test_clock_provider_is_abstract(self):
        with pytest.raises(TypeError):
            ClockProvider()  # type: ignore[abstract]


class TestRealClock:
    """RealClock returns actual wall-clock UTC times."""

    def test_utcnow_returns_datetime_with_utc_tz(self):
        clock = RealClock()
        now = clock.utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is UTC

    def test_utcnow_advances(self):
        """Two sequential calls return increasing timestamps."""
        clock = RealClock()
        t1 = clock.utcnow()
        t2 = clock.utcnow()
        assert t2 >= t1


class TestFakeClock:
    """FakeClock returns deterministic times for reproducible tests."""

    def test_default_epoch(self):
        """Default FakeClock returns 2025-01-01T00:00:00Z."""
        clock = FakeClock()
        assert clock.utcnow() == datetime(2025, 1, 1, tzinfo=UTC)

    def test_fixed_datetime(self):
        """FakeClock returns the datetime it was initialised with."""
        fixed = datetime(2024, 6, 15, 12, 30, 0, tzinfo=UTC)
        clock = FakeClock(now=fixed)
        assert clock.utcnow() == fixed

    def test_immutable(self):
        """Repeated calls to utcnow() return the same value."""
        fixed = datetime(2024, 1, 1, tzinfo=UTC)
        clock = FakeClock(now=fixed)
        for _ in range(10):
            assert clock.utcnow() == fixed

    def test_injectable_via_init(self):
        """FakeClock can be passed as a ClockProvider dependency."""

        class UsesClock:
            def __init__(self, clock: ClockProvider) -> None:
                self._clock = clock

            def get_time(self) -> datetime:
                return self._clock.utcnow()

        clock = FakeClock(now=datetime(2023, 12, 25, tzinfo=UTC))
        obj = UsesClock(clock)
        assert obj.get_time() == datetime(2023, 12, 25, tzinfo=UTC)

    def test_can_advance_by_setting_new_now(self):
        """Replacing _now simulates time progression."""
        clock = FakeClock()
        t1 = clock.utcnow()
        clock._now = t1 + timedelta(hours=1)
        t2 = clock.utcnow()
        assert t2 - t1 == timedelta(hours=1)
