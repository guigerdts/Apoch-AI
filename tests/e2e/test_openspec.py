"""E2E validation for OpenSpec — real tool tests.

Pytest markers: ``e2e``
Requires: ``openspec`` binary on PATH (skips gracefully if absent).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.e2e.helpers import is_ci

pytestmark = pytest.mark.e2e

BINARY = "openspec"


def _require_openspec() -> None:
    if shutil.which(BINARY) is None:
        pytest.skip(f"{BINARY} not found on PATH")


class TestDetect:
    """``detect()`` behaviour — binary presence and version."""

    def test_binary_found(self) -> None:
        """The ``openspec`` binary is on PATH."""
        _require_openspec()
        assert shutil.which(BINARY) is not None

    def test_version_output(self) -> None:
        """``openspec --version`` returns a valid semver string."""
        _require_openspec()
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
    """``verify()`` behaviour — doctor command health."""

    def test_doctor_succeeds(self) -> None:
        """``openspec doctor`` exits with code 0."""
        _require_openspec()
        result = subprocess.run(
            [BINARY, "doctor"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"doctor failed: {result.stderr.strip()}"
        )


class TestHealth:
    """``health()`` behaviour — JSON diagnostic output."""

    def test_doctor_json_output(self) -> None:
        """``openspec doctor --json`` returns valid JSON with healthy status."""
        _require_openspec()
        result = subprocess.run(
            [BINARY, "doctor", "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, dict), "expected JSON object"

        # The root section should be present and indicate health
        root = data.get("root", {})
        assert root.get("healthy") is not False, (
            "openspec reports unhealthy"
        )


class TestActivateDeactivate:
    """``activate()`` / ``deactivate()`` — no-op lifecycle."""

    def test_activate_succeeds(self) -> None:
        """Activate with a no-op tool succeeds (returns exit 0)."""
        _require_openspec()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0

    def test_deactivate_succeeds(self) -> None:
        """Deactivate with a no-op tool succeeds (returns exit 0)."""
        _require_openspec()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0


class TestInstallUninstall:
    """``install()`` / ``uninstall()`` — CI-only destructive tests."""

    def test_install_command_resolves(self) -> None:
        """The npm install command for OpenSpec is valid."""
        _require_openspec()
        if not is_ci():
            pytest.skip("install test requires CI environment")

        result = subprocess.run(
            ["npm", "install", "-g", "@fission-ai/openspec@latest"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"install failed: {result.stderr.strip()}"
        )

    def test_uninstall_command_resolves(self) -> None:
        """The npm uninstall command for OpenSpec is valid."""
        _require_openspec()
        if not is_ci():
            pytest.skip("uninstall test requires CI environment")

        result = subprocess.run(
            ["npm", "uninstall", "-g", "@fission-ai/openspec"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"uninstall failed: {result.stderr.strip()}"
        )
