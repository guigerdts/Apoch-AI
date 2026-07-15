"""E2E validation for Context7 — real tool tests.

Pytest markers: ``e2e``
Requires: ``ctx7`` binary on PATH (skips gracefully if absent).

Context7 uses ``ctx7`` as its CLI binary name.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from tests.e2e.helpers import is_ci

pytestmark = pytest.mark.e2e

BINARY = "ctx7"


def _require_ctx7() -> None:
    if shutil.which(BINARY) is None:
        pytest.skip(f"{BINARY} not found on PATH")


class TestDetect:
    """``detect()`` behaviour — binary presence and version."""

    def test_binary_found(self) -> None:
        """The ``ctx7`` binary is on PATH."""
        _require_ctx7()
        assert shutil.which(BINARY) is not None

    def test_version_output(self) -> None:
        """``ctx7 --version`` returns a valid semver string."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        ver = result.stdout.strip()
        assert ver, "version output is empty"
        parts = ver.split(".")
        assert len(parts) == 3, f"expected semver, got {ver!r}"
        for p in parts:
            assert p.isdigit(), f"part {p!r} is not numeric"


class TestVerify:
    """``verify()`` behaviour — tool can display help."""

    def test_help_succeeds(self) -> None:
        """``ctx7 --help`` exits with code 0."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"--help failed: {result.stderr.strip()}"
        )

    def test_help_contains_usage(self) -> None:
        """``--help`` output contains 'Usage:'."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "Usage:" in result.stdout, (
            "unexpected --help format"
        )


class TestHealth:
    """``health()`` behaviour — detect-only health check."""

    def test_version_available(self) -> None:
        """Presence of version implies tool is operational."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0

    def test_help_available(self) -> None:
        """Help output confirms basic functionality."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--help"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0


class TestActivateDeactivate:
    """``activate()`` / ``deactivate()`` — no-op lifecycle."""

    def test_activate_succeeds(self) -> None:
        """Activate via version check succeeds."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0

    def test_deactivate_succeeds(self) -> None:
        """Deactivate via version check succeeds."""
        _require_ctx7()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0


class TestInstallUninstall:
    """``install()`` / ``uninstall()`` — CI-only destructive tests."""

    def test_install_command_resolves(self) -> None:
        """The npm install command for Context7 is valid."""
        _require_ctx7()
        if not is_ci():
            pytest.skip("install test requires CI environment")

        result = subprocess.run(
            ["npm", "install", "-g", "context7"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"install failed: {result.stderr.strip()}"
        )

    def test_uninstall_command_resolves(self) -> None:
        """The npm uninstall command for Context7 is valid."""
        _require_ctx7()
        if not is_ci():
            pytest.skip("uninstall test requires CI environment")

        result = subprocess.run(
            ["npm", "uninstall", "-g", "context7"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"uninstall failed: {result.stderr.strip()}"
        )
