"""Smoke tests for E2E infrastructure.

These tests validate that the fixtures, helpers, and markers work
correctly — they do NOT call any real tool.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.e2e.helpers import find_binary, is_ci, requires_tool, sandbox_env


class TestHelpers:
    """Helper functions — no external dependencies."""

    def test_find_binary_known(self) -> None:
        """``find_binary`` should find ``python`` (always on PATH in test env)."""
        found = find_binary("python")
        assert found is not None
        assert isinstance(found, Path)
        assert found.name.startswith("python")

    def test_find_binary_unknown(self) -> None:
        """``find_binary`` should return ``None`` for a non-existent tool."""
        assert find_binary("this-tool-does-not-exist-12345") is None

    def test_requires_tool_present(self) -> None:
        """``requires_tool`` returns the name when the tool exists."""
        assert requires_tool("python") == "python"

    def test_requires_tool_absent(self) -> None:
        """``requires_tool`` returns ``None`` when the tool is missing."""
        assert requires_tool("this-tool-does-not-exist-12345") is None

    def test_is_ci_default(self) -> None:
        """``is_ci`` should be ``False`` when ``CI`` is not set."""
        assert is_ci() is False

    def test_is_ci_override(self, ci_override: None) -> None:
        """``is_ci`` should be ``True`` when ``CI`` is set."""
        assert is_ci() is True

    def test_sandbox_env_sets_and_restores(self) -> None:
        """``sandbox_env`` should set a var during the block and restore after."""
        key = "_APOCH_E2E_TEST_VAR"
        assert os.environ.get(key) is None

        with sandbox_env(**{key: "present"}):
            assert os.environ.get(key) == "present"

        assert os.environ.get(key) is None


class TestFixtures:
    """Conftest fixtures — no real tool calls."""

    def test_apoch_root(self, apoch_root: Path) -> None:
        """``apoch_root`` should point to the repo root."""
        assert (apoch_root / "pyproject.toml").exists()
        assert (apoch_root / "src" / "apoch").is_dir()

    def test_sandbox_path_is_empty(self, sandbox_path: Path) -> None:
        """``sandbox_path`` should start empty."""
        assert sandbox_path.is_dir()
        assert list(sandbox_path.iterdir()) == []  # noqa: SIM115

    def test_isolated_env_restricts_path(self, isolated_env: dict[str, str]) -> None:
        """Under ``isolated_env``, system tools are invisible."""
        import shutil
        # The sandbox bin/ is empty, so even ``python`` should not resolve.
        assert shutil.which("python") is None

    @pytest.mark.e2e
    def test_skip_if_no_openspec(self, skip_if_no_openspec: bool) -> None:
        """``skip_if_no_openspec`` skips when OpenSpec is absent.

        Under the ``isolated_env`` fixture this will skip because OpenSpec
        is not in the sandbox PATH.  That is correct infrastructure
        behaviour — the skip is the feature being tested.
        """

    @pytest.mark.e2e
    def test_e2e_marker_registered(self) -> None:
        """``@pytest.mark.e2e`` is recognised and does not raise.

        This test exists solely to confirm the marker is registered.
        It does NOT call any real tool.
        """
        assert True
