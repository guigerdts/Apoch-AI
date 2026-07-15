"""Shared fixtures for Stack component tests."""

from __future__ import annotations

import pytest

from apoch.stack.registry import StackRegistry


@pytest.fixture
def registry() -> StackRegistry:
    """Create a fresh ``StackRegistry``.

    Available to all tests in ``tests/stack/`` via conftest discovery.
    """
    return StackRegistry()
