"""Tests for Pulse data models — invariants, privacy, and constraints.

Spec: pulse-productivity-intelligence §R1–R11
Design: Pulse — Engineering Productivity Intelligence §Append-only
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from apoch.modules.pulse.models import MeasurementInput, WorkUnit, WorkUnitFilter


class TestWorkUnit:
    """WorkUnit is the immutable measurement record (append-only)."""

    def test_frozen_immutability(self) -> None:
        """WorkUnit MUST be immutable after creation (append-only)."""
        unit = WorkUnit(
            id="u1", session_id="s1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        )
        with pytest.raises(FrozenInstanceError):
            unit.tokens_input = 999

    def test_cost_may_be_none(self) -> None:
        """WorkUnit.cost MUST be None when the model has no configured price."""
        unit = WorkUnit(id="u1", session_id="s1", model="unknown-model",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        assert unit.cost is None

    def test_cost_may_be_decimal(self) -> None:
        """WorkUnit.cost SHOULD support Decimal for accurate monetary tracking."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                        cost=Decimal("0.015"))
        assert unit.cost == Decimal("0.015")

    def test_completed_at_none_when_in_progress(self) -> None:
        """WorkUnit.completed_at MUST be None for incomplete work units (R1)."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        assert unit.completed_at is None

    def test_privacy_no_content(self) -> None:
        """WorkUnit MUST NOT store session content (R9)."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        # No field for prompt text, response text, or code content
        assert not hasattr(unit, "content")
        assert not hasattr(unit, "prompt")
        assert not hasattr(unit, "response")

    def test_privacy_no_identity(self) -> None:
        """WorkUnit MUST NOT store developer identity (R9)."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        assert not hasattr(unit, "developer")
        assert not hasattr(unit, "email")
        assert not hasattr(unit, "author")

    def test_privacy_no_system_metrics(self) -> None:
        """WorkUnit MUST NOT store system performance metrics (R9)."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        assert not hasattr(unit, "cpu")
        assert not hasattr(unit, "memory")
        assert not hasattr(unit, "latency")

    def test_default_lines(self) -> None:
        """WorkUnit MUST default lines_original and lines_modified to 0 (R5)."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0)
        assert unit.lines_original == 0
        assert unit.lines_modified == 0

    def test_lines_backward_compatible(self) -> None:
        """WorkUnit with explicit line data MUST preserve them."""
        unit = WorkUnit(id="u1", session_id="s1", model="claude-4",
                        tokens_input=100, tokens_output=50, wall_clock_s=30.0,
                        lines_original=100, lines_modified=20)
        assert unit.lines_original == 100
        assert unit.lines_modified == 20


class TestMeasurementInput:
    """MeasurementInput is the mutable input before storage."""

    def test_input_fields(self) -> None:
        """MeasurementInput MUST carry all required measurement data."""
        inp = MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        )
        assert inp.session_id == "s1"
        assert inp.work_unit_id == "wu-1"
        assert inp.model == "claude-4"
        assert inp.tokens_input == 100
        assert inp.tokens_output == 50
        assert inp.wall_clock_s == 30.0
        assert inp.cost is None

    def test_input_with_cost(self) -> None:
        """MeasurementInput MAY carry a pre-computed cost."""
        inp = MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            cost=Decimal("0.015"),
        )
        assert inp.cost == Decimal("0.015")

    def test_input_default_lines(self) -> None:
        """MeasurementInput MUST default lines_original and lines_modified to 0."""
        inp = MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
        )
        assert inp.lines_original == 0
        assert inp.lines_modified == 0

    def test_input_with_lines(self) -> None:
        """MeasurementInput MAY carry line-based rework data."""
        inp = MeasurementInput(
            session_id="s1", work_unit_id="wu-1", model="claude-4",
            tokens_input=100, tokens_output=50, wall_clock_s=30.0,
            lines_original=100, lines_modified=20,
        )
        assert inp.lines_original == 100
        assert inp.lines_modified == 20


class TestWorkUnitFilter:
    """WorkUnitFilter provides query parameters (all optional)."""

    def test_default_filter(self) -> None:
        """WorkUnitFilter MUST default to no filters, limit 100."""
        f = WorkUnitFilter()
        assert f.session_id is None
        assert f.model is None
        assert f.since is None
        assert f.until is None
        assert f.limit == 100
