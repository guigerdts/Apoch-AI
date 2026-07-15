"""E2E validation for CodeGraph — real tool tests.

Pytest markers: ``e2e``
Requires: ``codegraph`` binary on PATH (skips gracefully if absent).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.e2e.helpers import is_ci

pytestmark = pytest.mark.e2e

BINARY = "codegraph"


def _require_codegraph() -> None:
    if shutil.which(BINARY) is None:
        pytest.skip(f"{BINARY} not found on PATH")


class TestDetect:
    """``detect()`` behaviour — binary presence and version."""

    def test_binary_found(self) -> None:
        """The ``codegraph`` binary is on PATH."""
        _require_codegraph()
        assert shutil.which(BINARY) is not None

    def test_version_output(self) -> None:
        """``codegraph --version`` returns a bare semver (no prefix)."""
        _require_codegraph()
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
    """``verify()`` behaviour — help command health."""

    def test_help_succeeds(self) -> None:
        """``codegraph --help`` exits with code 0."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"--help failed: {result.stderr.strip()}"
        )

    def test_help_contains_usage(self) -> None:
        """``--help`` output contains 'Usage:'."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "Usage:" in result.stdout, (
            "unexpected --help format"
        )


class TestHealth:
    """``health()`` behaviour — status JSON diagnostic."""

    def test_status_json_output(self) -> None:
        """``codegraph status --json`` returns valid JSON."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "status", "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, dict), "expected JSON object"

    def test_status_shows_initialized(self) -> None:
        """``codegraph status --json`` reports initialized: true."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "status", "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        assert data.get("initialized") is True, (
            "codegraph reports uninitialized"
        )

    def test_status_shows_file_count(self) -> None:
        """``codegraph status --json`` includes a positive file count."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "status", "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data.get("fileCount"), int), (
            "fileCount missing or not an integer"
        )
        assert data["fileCount"] > 0, (
            f"expected >0 files, got {data['fileCount']}"
        )

    def test_health_not_stale(self) -> None:
        """Index is not stale (pendingChanges is known)."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "status", "--json"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        pending = data.get("pendingChanges")
        assert pending is not None, "pendingChanges missing from status"


class TestActivateDeactivate:
    """``activate()`` / ``deactivate()`` — no-op lifecycle."""

    def test_activate_succeeds(self) -> None:
        """Activate via version check succeeds."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0

    def test_deactivate_succeeds(self) -> None:
        """Deactivate via version check succeeds."""
        _require_codegraph()
        result = subprocess.run(
            [BINARY, "--version"],
            capture_output=True, text=True, check=True,
        )
        assert result.returncode == 0


class TestInstallUninstall:
    """``install()`` / ``uninstall()`` — CI-only destructive tests."""

    def test_install_command_resolves(self) -> None:
        """The npm install command for CodeGraph is valid."""
        _require_codegraph()
        if not is_ci():
            pytest.skip("install test requires CI environment")

        result = subprocess.run(
            ["npm", "install", "-g", "@fission-ai/codegraph@latest"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"install failed: {result.stderr.strip()}"
        )

    def test_uninstall_command_resolves(self) -> None:
        """The npm uninstall command for CodeGraph is valid."""
        _require_codegraph()
        if not is_ci():
            pytest.skip("uninstall test requires CI environment")

        result = subprocess.run(
            ["npm", "uninstall", "-g", "@fission-ai/codegraph"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"uninstall failed: {result.stderr.strip()}"
        )
