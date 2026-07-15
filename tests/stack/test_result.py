"""Tests for OperationResult dataclass.

Spec: core-stack §Structured Operation Results
Design: Core Stack Installation & Lifecycle — Structured Operation Results
"""

from __future__ import annotations

import pytest

from apoch.stack.result import OperationResult


class TestOperationResult:
    """Verify OperationResult creation and behaviour."""

    def test_success_result(self):
        """Create a successful operation result."""
        result = OperationResult(
            success=True,
            component="engram",
            message="Engram installed successfully",
            details={"version": "1.0.0", "path": "/home/user/.apoch/stack/engram"},
        )
        assert result.success is True
        assert result.component == "engram"
        assert "installed" in result.message
        assert result.details["version"] == "1.0.0"

    def test_failure_result(self):
        """Create a failed operation result."""
        result = OperationResult(
            success=False,
            component="oracle",
            message="Failed to install oracle: timeout",
            details={"error": "Connection timed out after 30s"},
        )
        assert result.success is False
        assert "timeout" in result.message
        assert result.details["error"] is not None

    def test_minimal_result(self):
        """Create a result without details."""
        result = OperationResult(
            success=True,
            component="test",
            message="Done",
        )
        assert result.details == {}

    def test_is_frozen(self):
        """OperationResult is immutable."""
        result = OperationResult(
            success=True,
            component="c",
            message="ok",
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_equality(self):
        """Two results with the same fields are equal."""
        a = OperationResult(success=True, component="x", message="ok")
        b = OperationResult(success=True, component="x", message="ok")
        assert a == b
