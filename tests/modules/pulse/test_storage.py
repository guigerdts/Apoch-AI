"""Tests for PulseStore — append-only measurement persistence.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §Append-only
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apoch.core.exceptions import StorageError
from apoch.modules.pulse.models import MeasurementInput, WorkUnitFilter
from apoch.modules.pulse.storage import PulseStore


class TestSave:
    """PulseStore.save() — append-only write."""

    def test_save_returns_work_unit(self) -> None:
        """save() MUST return a populated WorkUnit."""
        store = PulseStore()
        unit = store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        assert unit.id == "wu-1"
        assert unit.session_id == "s1"
        assert unit.model == "claude-4"
        assert unit.tokens_input == 100
        assert unit.tokens_output == 50
        assert unit.wall_clock_s == 30.0
        assert unit.created_at != ""

    def test_save_with_cost(self) -> None:
        """save() MUST preserve optional cost."""
        store = PulseStore()
        unit = store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.015"),
        ))
        assert unit.cost == Decimal("0.015")

    def test_save_raises_on_duplicate(self) -> None:
        """save() MUST reject duplicate work_unit_id (append-only)."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-dup", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        with pytest.raises(StorageError, match="already exists"):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id="wu-dup", model="claude-4",
                tokens_input=200, tokens_output=100, wall_clock_s=45.0,
            ))

    def test_save_append_only_no_overwrite(self) -> None:
        """save() MUST preserve the first record (append-only immutability)."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-immutable", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        with pytest.raises(StorageError):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id="wu-immutable", model="gpt-4",
                tokens_input=999, tokens_output=999, wall_clock_s=99.0,
            ))
        # First record is still intact
        unit = store.get("wu-immutable")
        assert unit is not None
        assert unit.model == "claude-4"
        assert unit.tokens_input == 100


class TestGet:
    """PulseStore.get() — read by ID."""

    def test_get_returns_unit(self) -> None:
        """get() MUST return the stored WorkUnit."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        unit = store.get("wu-1")
        assert unit is not None
        assert unit.id == "wu-1"

    def test_get_returns_none_for_unknown(self) -> None:
        """get() MUST return None for a non-existent ID."""
        store = PulseStore()
        assert store.get("nonexistent") is None


class TestList:
    """PulseStore.list() — filtered read."""

    def test_list_empty(self) -> None:
        """list() MUST return empty list when store is empty."""
        store = PulseStore()
        assert store.list() == []

    def test_list_all(self) -> None:
        """list() MUST return all stored WorkUnits (up to default limit)."""
        store = PulseStore()
        for i in range(3):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        assert len(store.list()) == 3

    def test_list_by_session(self) -> None:
        """list() MUST filter by session_id."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s-a", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s-b", work_unit_id="wu-2", model="claude-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        result = store.list(WorkUnitFilter(session_id="s-a"))
        assert len(result) == 1
        assert result[0].session_id == "s-a"

    def test_list_by_model(self) -> None:
        """list() MUST filter by model."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s1", work_unit_id="wu-2", model="gpt-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        result = store.list(WorkUnitFilter(model="gpt-4"))
        assert len(result) == 1
        assert result[0].model == "gpt-4"

    def test_list_with_limit(self) -> None:
        """list() MUST cap results at the configured limit."""
        store = PulseStore()
        for i in range(10):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        result = store.list(WorkUnitFilter(limit=3))
        assert len(result) == 3

    def test_list_newest_first(self) -> None:
        """list() MUST return results newest first."""
        store = PulseStore()
        for i in range(3):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        result = store.list()
        timestamps = [u.created_at for u in result]
        assert timestamps == sorted(timestamps, reverse=True)


class TestCount:
    """PulseStore.count() — count matching records."""

    def test_count_zero(self) -> None:
        """count() MUST return 0 on empty store."""
        store = PulseStore()
        assert store.count() == 0

    def test_count_all(self) -> None:
        """count() MUST return total record count."""
        store = PulseStore()
        for i in range(5):
            store.save(MeasurementInput(
                session_id="s1", work_unit_id=f"wu-{i}", model="claude-4",
                tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            ))
        assert store.count() == 5

    def test_count_with_filter(self) -> None:
        """count() MUST respect filter criteria."""
        store = PulseStore()
        store.save(MeasurementInput(
            session_id="s-a", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        ))
        store.save(MeasurementInput(
            session_id="s-b", work_unit_id="wu-2", model="gpt-4",
            tokens_input=200, tokens_output=100, wall_clock_s=60.0,
        ))
        assert store.count(WorkUnitFilter(session_id="s-a")) == 1
        assert store.count(WorkUnitFilter(model="gpt-4")) == 1


class TestNoAnalysisMethods:
    """PulseStore MUST NOT expose analysis methods."""

    def test_no_trend_method(self) -> None:
        """PulseStore MUST NOT have a trend/analyze method (Analysis owns this)."""
        store = PulseStore()
        assert not hasattr(store, "trend")
        assert not hasattr(store, "analyze")
        assert not hasattr(store, "rework")
        assert not hasattr(store, "aggregate")
