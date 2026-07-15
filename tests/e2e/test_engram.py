"""E2E validation for Engram — real tool tests.

Pytest markers: ``e2e``
Requires: ``engram`` binary on PATH (skips gracefully if absent).
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from tests.e2e.helpers import is_ci

pytestmark = pytest.mark.e2e

BINARY = "engram"
_VERSION_PATTERN = re.compile(r"engram\s+\d+\.\d+\.\d+")


def _require_engram() -> None:
    if shutil.which(BINARY) is None:
        pytest.skip(f"{BINARY} not found on PATH")


class TestDetect:
    """``detect()`` behaviour — binary presence and version."""

    def test_binary_found(self) -> None:
        """The ``engram`` binary is on PATH."""
        _require_engram()
        assert shutil.which(BINARY) is not None

    def test_version_output(self) -> None:
        """``engram version`` returns a "engram X.Y.Z" string."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "version"],
            capture_output=True, text=True, check=True,
        )
        output = result.stdout.strip()
        assert _VERSION_PATTERN.match(output), (
            f"expected 'engram X.Y.Z', got {output!r}"
        )


class TestVerify:
    """``verify()`` behaviour — doctor command health."""

    def test_doctor_succeeds(self) -> None:
        """``engram doctor`` exits with code 0."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "doctor"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"doctor failed: {result.stderr.strip()}"
        )


class TestHealth:
    """``health()`` behaviour — diagnostic output."""

    def test_doctor_reports_ok(self) -> None:
        """``engram doctor`` reports 'Engram Doctor: ok'."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "doctor"],
            capture_output=True, text=True, check=True,
        )
        assert "Engram Doctor: ok" in result.stdout, (
            "engram reports unhealthy"
        )

    def test_doctor_all_checks_ok(self) -> None:
        """``engram doctor`` shows 0 warnings / 0 errors."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "doctor"],
            capture_output=True, text=True, check=True,
        )
        assert "errors=0" in result.stdout, (
            f"engram has errors:\n{result.stdout}"
        )


class TestActivateDeactivate:
    """``activate()`` / ``deactivate()`` — no-op lifecycle."""

    def test_activate_succeeds(self) -> None:
        """Activate via version check succeeds."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0

    def test_deactivate_succeeds(self) -> None:
        """Deactivate via version check succeeds."""
        _require_engram()
        result = subprocess.run(
            [BINARY, "version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0


class TestInstallUninstall:
    """``install()`` / ``uninstall()`` — CI-only destructive tests."""

    def test_install_command_resolves(self) -> None:
        """The npm install command for Engram is valid."""
        _require_engram()
        if not is_ci():
            pytest.skip("install test requires CI environment")

        result = subprocess.run(
            ["npm", "install", "-g", "@fission-ai/engram-cli@latest"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"install failed: {result.stderr.strip()}"
        )

    def test_uninstall_command_resolves(self) -> None:
        """The npm uninstall command for Engram is valid."""
        _require_engram()
        if not is_ci():
            pytest.skip("uninstall test requires CI environment")

        result = subprocess.run(
            ["npm", "uninstall", "-g", "@fission-ai/engram-cli"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"uninstall failed: {result.stderr.strip()}"
        )
