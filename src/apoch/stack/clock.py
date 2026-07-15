"""Injectable clock abstraction for deterministic time in tests.

Design: Core Stack Installation & Lifecycle — ClockProvider
Principle: All timestamps obtained through ``ClockProvider``,
never ``datetime.now()`` directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime


class ClockProvider(ABC):
    """Injectable clock — allows deterministic time in tests.

    Usage::

        class MyClass:
            def __init__(self, clock: ClockProvider | None = None) -> None:
                self._clock = clock or RealClock()
    """

    @abstractmethod
    def utcnow(self) -> datetime:
        """Return the current UTC datetime."""
        ...


class RealClock(ClockProvider):
    """Production clock that returns the real wall-clock time."""

    def utcnow(self) -> datetime:
        """Return the current UTC time via :func:`datetime.now`."""
        return datetime.now(UTC)


class FakeClock(ClockProvider):
    """Deterministic clock for tests.

    Accepts a fixed datetime that ``utcnow()`` always returns, or a
    callable that produces a sequence of datetimes.
    """

    def __init__(self, now: datetime | None = None) -> None:
        """Initialise with an optional fixed datetime.

        Args:
            now: Fixed value returned by ``utcnow()``.  Defaults to
                 ``datetime(2025, 1, 1, tzinfo=UTC)``.
        """
        self._now = now or datetime(2025, 1, 1, tzinfo=UTC)

    def utcnow(self) -> datetime:
        """Return the fixed datetime this clock was created with."""
        return self._now


__all__ = [
    "ClockProvider",
    "FakeClock",
    "RealClock",
]
