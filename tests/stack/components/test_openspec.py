"""Tests for the OpenSpec Stack Component.

PR5.1 — Foundation: DESCRIPTOR, parse_openspec_version, and
entry-point resolution.

PR5.3 — Lifecycle: detect, install, uninstall, verify, health,
activate, and deactivate via MockRunner.
"""

from __future__ import annotations

import json
from pathlib import Path

from apoch.stack.components.openspec import (
    DESCRIPTOR,
    OpenSpecComponent,
    parse_openspec_version,
)
from apoch.stack.runner import MockRunner, RunResult

# ── Foundation: Descriptor ────────────────────────────────────────────


class TestDescriptor:
    """DESCRIPTOR contains factual metadata about the official project."""

    def test_id(self):
        assert DESCRIPTOR.id == "openspec"

    def test_name(self):
        assert DESCRIPTOR.name == "OpenSpec"

    def test_kind(self):
        assert DESCRIPTOR.kind == "integrations"

    def test_install_command(self):
        assert "npm install -g" in DESCRIPTOR.install_command

    def test_homepage(self):
        assert DESCRIPTOR.homepage == "https://openspec.dev/"

    def test_repository(self):
        assert "github.com/fission-ai/OpenSpec" in DESCRIPTOR.repository

    def test_requires_node(self):
        assert "node" in DESCRIPTOR.requires[0]


# ── Foundation: Version parser ────────────────────────────────────────


class TestParseVersion:
    """parse_openspec_version handles multiple output formats."""

    def test_openspec_prefix(self):
        assert parse_openspec_version("openspec 1.6.0") == "1.6.0"

    def test_v_prefix(self):
        assert parse_openspec_version("v1.6.0") == "1.6.0"

    def test_bare(self):
        assert parse_openspec_version("1.6.0") == "1.6.0"

    def test_multiline(self):
        assert parse_openspec_version("foo\nopenspec 1.6.0\nbar") == "1.6.0"

    def test_nonsense(self):
        assert parse_openspec_version("not-a-version") is None

    def test_empty(self):
        assert parse_openspec_version("") is None


# ── Foundation: Component instantiation ───────────────────────────────


class TestComponent:
    """OpenSpecComponent can be instantiated and has correct descriptor."""

    def test_descriptor_is_descriptor(self):
        comp = OpenSpecComponent()
        assert comp.descriptor is DESCRIPTOR

    def test_default_runner_is_real_runner(self):
        comp = OpenSpecComponent()
        from apoch.stack.runner import RealRunner

        assert isinstance(comp._runner, RealRunner)

    def test_custom_runner_injected(self):
        runner = MockRunner()
        comp = OpenSpecComponent(runner=runner)
        assert comp._runner is runner


# ── Foundation: Entry point ───────────────────────────────────────────


class TestEntryPoint:
    """The entry point resolves correctly via importlib.metadata."""

    def test_entry_point_resolves(self):
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.stack.components")
        openspec_eps = [ep for ep in eps if ep.name == "openspec"]
        assert len(openspec_eps) == 1
        ep = openspec_eps[0]
        assert ep.value == "apoch.stack.components.openspec:OpenSpecComponent"


# ── Lifecycle: detect ─────────────────────────────────────────────────


class TestDetect:
    """OpenSpecComponent.detect() observes the local system."""

    async def test_not_installed_when_binary_missing(self, monkeypatch):
        comp = OpenSpecComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        info = await comp.detect()
        assert info.installed is False

    async def test_installed_when_binary_found(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version == "1.5.0"
        assert info.executable_path == Path("/usr/local/bin/openspec")

    async def test_detect_fails_when_version_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="error"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        info = await comp.detect()
        assert info.installed is False
        assert "version check failed" in (info.metadata.get("error") or "")

    async def test_unparseable_version_returns_none(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="OpenSpec Nightly\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version is None
        assert info.executable_path == Path("/usr/local/bin/openspec")


# ── Lifecycle: install ────────────────────────────────────────────────


class TestInstall:
    """OpenSpecComponent.install() delegates to npm."""

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.install()
        assert result.success is True
        assert result.component == "openspec"
        assert "installed" in result.message

    async def test_install_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="npm ERR!"))
        comp = OpenSpecComponent(runner=runner)
        result = await comp.install()
        assert result.success is False
        assert "failed" in result.message

    async def test_binary_found_but_version_not_parseable(self, monkeypatch):
        """Install succeeds but version is unparseable → failure."""
        runner = MockRunner(result=RunResult(returncode=0, stdout="internal build\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.install()
        assert result.success is False
        assert "version could not be parsed" in result.message

    async def test_binary_not_found_after_install(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        result = await comp.install()
        assert result.success is False
        assert "binary not found" in result.message


# ── Lifecycle: uninstall ──────────────────────────────────────────────


class TestUninstall:
    """OpenSpecComponent.uninstall() delegates to npm."""

    async def test_not_installed_returns_success(self, monkeypatch):
        comp = OpenSpecComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "not installed" in result.message

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "uninstalled" in result.message

    async def test_uninstall_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )

        async def _run(cmd, *, timeout=None, env=None):
            if cmd[0] == "openspec":
                return RunResult(returncode=0, stdout="1.5.0\n")
            return RunResult(returncode=1, stderr="permission denied")

        runner.run = _run

        result = await comp.uninstall()
        assert result.success is False
        assert "failed" in result.message


# ── Lifecycle: verify ─────────────────────────────────────────────────


class TestVerify:
    """OpenSpecComponent.verify() validates the installation."""

    async def test_not_installed(self, monkeypatch):
        comp = OpenSpecComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        result = await comp.verify()
        assert result.success is False
        assert "not installed" in result.message

    async def test_verify_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.verify()
        assert result.success is True
        assert "verified" in result.message

    async def test_doctor_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )

        async def _fail_doctor(cmd, *, timeout=None, env=None):
            if "doctor" in cmd:
                return RunResult(returncode=1, stderr="doctor failed")
            return RunResult(returncode=0, stdout="1.5.0\n")

        runner.run = _fail_doctor

        result = await comp.verify()
        assert result.success is False
        assert "doctor failed" in result.message

    async def test_skip_async_still_runs_doctor(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.verify(skip_async=True)
        assert result.success is True
        assert "verified" in result.message


# ── Lifecycle: health ─────────────────────────────────────────────────


class TestHealth:
    """OpenSpecComponent.health() returns a diagnostic dict."""

    @staticmethod
    def _make_runner(
        doctor_stdout: str = "",
        doctor_retcode: int = 0,
        *,
        version: str = "1.5.0\n",
    ) -> MockRunner:
        """Build a runner that returns version output for detect and
        doctor output for the health check."""
        runner = MockRunner()

        async def _run(cmd, *, timeout=None, env=None):
            if "--version" in cmd:
                return RunResult(returncode=0, stdout=version)
            return RunResult(returncode=doctor_retcode, stdout=doctor_stdout)

        runner.run = _run
        return runner

    async def test_down_when_not_installed(self, monkeypatch):
        comp = OpenSpecComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        status = await comp.health()
        assert status["status"] == "down"
        assert status["component"] == "openspec"

    async def test_healthy_via_json(self, monkeypatch):
        """JSON mode: valid JSON with healthy=true → healthy."""
        doctor_data = {"root": {"healthy": True, "path": "/repo"}, "status": []}
        runner = self._make_runner(doctor_stdout=json.dumps(doctor_data))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "1.5.0"
        assert status["diagnostics"]["root"]["healthy"] is True

    async def test_degraded_via_json(self, monkeypatch):
        """JSON mode: valid JSON with healthy=false → degraded."""
        doctor_data = {"root": {"healthy": False, "path": "/repo"}, "status": ["error"]}
        runner = self._make_runner(doctor_stdout=json.dumps(doctor_data))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        status = await comp.health()
        assert status["status"] == "degraded"
        assert status["version"] == "1.5.0"
        assert status["diagnostics"]["root"]["healthy"] is False

    async def test_json_no_healthy_field_falls_back(self, monkeypatch):
        """JSON mode: valid JSON without healthy field → fallback to exit code."""
        doctor_data = {"status": [], "root": {"path": "/repo"}}
        runner = self._make_runner(doctor_stdout=json.dumps(doctor_data))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        status = await comp.health()
        # Fallback runs doctor — exit code 0 → healthy
        assert status["status"] == "healthy"
        assert status["version"] == "1.5.0"

    async def test_json_invalid_falls_back(self, monkeypatch):
        """JSON mode: invalid JSON → fallback to exit code."""
        runner = self._make_runner(doctor_stdout="not json\n")
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "1.5.0"

    async def test_json_fallback_degraded_on_bad_exit(self, monkeypatch):
        """JSON mode: fallback exit code is non-zero → degraded."""
        runner = self._make_runner(doctor_stdout="failed\n", doctor_retcode=1)
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        status = await comp.health()
        assert status["status"] == "degraded"
        assert status["version"] == "1.5.0"
        assert status["diagnostics"]["doctor_exit"] == 1


# ── Lifecycle: activate / deactivate ──────────────────────────────────


class TestActivate:
    """OpenSpecComponent.activate() verifies the binary is operational."""

    async def test_activate_when_installed(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.5.0\n"))
        comp = OpenSpecComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: "/usr/local/bin/openspec",
        )
        result = await comp.activate()
        assert result.success is True
        assert "active" in result.message

    async def test_activate_fails_when_not_installed(self, monkeypatch):
        comp = OpenSpecComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.openspec.shutil.which",
            lambda cmd: None,
        )
        result = await comp.activate()
        assert result.success is False
        assert "not installed" in result.message


class TestDeactivate:
    """OpenSpecComponent.deactivate() is a no-op (CLI binary, no session)."""

    async def test_deactivate_always_succeeds(self):
        comp = OpenSpecComponent(runner=MockRunner())
        result = await comp.deactivate()
        assert result.success is True
        assert "deactivated" in result.message
