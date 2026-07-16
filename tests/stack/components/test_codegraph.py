"""Tests for the CodeGraph Stack Component.

DESCRIPTOR, _parse_version, entry-point resolution, and full lifecycle
(detect, health, install, uninstall, verify, activate, deactivate).
"""

from __future__ import annotations

import json
from pathlib import Path

from apoch.stack.components.codegraph import (
    CODEGRAPH_DESCRIPTOR,
    CodeGraphComponent,
    _parse_version,
)
from apoch.stack.runner import MockRunner, RunResult

# ── Foundation: Descriptor ────────────────────────────────────────────


class TestDescriptor:
    """CODEGRAPH_DESCRIPTOR contains factual metadata about the official project."""

    def test_descriptor_fields(self):
        assert CODEGRAPH_DESCRIPTOR.id == "codegraph"
        assert CODEGRAPH_DESCRIPTOR.name == "CodeGraph"
        assert CODEGRAPH_DESCRIPTOR.kind == "integrations"
        assert CODEGRAPH_DESCRIPTOR.version == "1.4.1"
        assert "npm install -g" in CODEGRAPH_DESCRIPTOR.install_command
        assert CODEGRAPH_DESCRIPTOR.capabilities == (
            "code-intelligence",
            "knowledge-graph",
            "mcp",
        )
        assert CODEGRAPH_DESCRIPTOR.requires == ("node",)
        assert (
            CODEGRAPH_DESCRIPTOR.homepage
            == "https://colbymchenry.github.io/codegraph/"
        )
        assert "github.com/colbymchenry/codegraph" in CODEGRAPH_DESCRIPTOR.repository

    def test_descriptor_is_frozen(self):
        from apoch.stack.components.codegraph import (
            CODEGRAPH_DESCRIPTOR as CODEGRAPH_DESCRIPTOR_AGAIN,
        )

        assert CODEGRAPH_DESCRIPTOR is CODEGRAPH_DESCRIPTOR_AGAIN


# ── Foundation: Version parser ────────────────────────────────────────


class TestParseVersion:
    """_parse_version handles CodeGraph output formats."""

    def test_parse_version_bare_semver(self):
        assert _parse_version("1.3.1") == "1.3.1"

    def test_parse_version_with_v_prefix(self):
        assert _parse_version("v1.3.1") == "1.3.1"

    def test_parse_version_multiline(self):
        assert _parse_version("foo\n1.3.1\nbar") == "1.3.1"

    def test_parse_version_nonsense(self):
        assert _parse_version("not a version") is None

    def test_parse_version_empty(self):
        assert _parse_version("") is None


# ── Foundation: Component instantiation ───────────────────────────────


class TestComponent:
    """CodeGraphComponent can be instantiated and has correct descriptor."""

    def test_component_default_runner(self):
        comp = CodeGraphComponent()
        from apoch.stack.runner import RealRunner

        assert isinstance(comp._runner, RealRunner)

    def test_component_custom_runner(self):
        runner = MockRunner()
        comp = CodeGraphComponent(runner=runner)
        assert comp._runner is runner

    def test_component_descriptor(self):
        comp = CodeGraphComponent()
        assert comp.descriptor is CODEGRAPH_DESCRIPTOR


# ── Foundation: Entry point ───────────────────────────────────────────


class TestEntryPoint:
    """The entry point resolves correctly via importlib.metadata."""

    def test_entry_point_resolution(self):
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.stack.components")
        codegraph_eps = [ep for ep in eps if ep.name == "codegraph"]
        assert len(codegraph_eps) == 1
        ep = codegraph_eps[0]
        assert ep.value == "apoch.stack.components.codegraph:CodeGraphComponent"


# ── Lifecycle: detect ─────────────────────────────────────────────────


class TestDetect:
    """CodeGraphComponent.detect() observes the local system."""

    async def test_not_installed_when_binary_missing(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        info = await comp.detect()
        assert info.installed is False

    async def test_installed_when_binary_found(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version == "1.3.1"
        assert info.executable_path == Path("/usr/local/bin/codegraph")

    async def test_detect_fails_when_version_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="error"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        info = await comp.detect()
        assert info.installed is False
        assert "version check failed" in (info.metadata.get("error") or "")

    async def test_unparseable_version_returns_none(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="CodeGraph Nightly\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version is None
        assert info.executable_path == Path("/usr/local/bin/codegraph")


# ── Lifecycle: install ────────────────────────────────────────────────


class TestInstall:
    """CodeGraphComponent.install() delegates to npm."""

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        result = await comp.install()
        assert result.success is True
        assert result.component == "codegraph"
        assert "installed" in result.message

    async def test_install_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="npm ERR!"))
        comp = CodeGraphComponent(runner=runner)
        result = await comp.install()
        assert result.success is False
        assert "failed" in result.message

    async def test_binary_not_found_after_install(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        result = await comp.install()
        assert result.success is False
        assert "binary not found" in result.message


# ── Lifecycle: verify ─────────────────────────────────────────────────


class TestVerify:
    """CodeGraphComponent.verify() validates the installation."""

    async def test_not_installed(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        result = await comp.verify()
        assert result.success is False
        assert "not installed" in result.message

    async def test_verify_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        result = await comp.verify()
        assert result.success is True
        assert "verified" in result.message

    async def test_help_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )

        async def _fail_help(cmd, *, timeout=None, env=None):
            if "--help" in cmd:
                return RunResult(returncode=1, stderr="unknown option")
            return RunResult(returncode=0, stdout="1.3.1\n")

        runner.run = _fail_help

        result = await comp.verify()
        assert result.success is False
        assert "failed" in result.message


# ── Lifecycle: activate / deactivate ──────────────────────────────────


class TestActivate:
    """CodeGraphComponent.activate() verifies the binary is operational."""

    async def test_activate_when_installed(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        result = await comp.activate()
        assert result.success is True
        assert "active" in result.message

    async def test_activate_fails_when_not_installed(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        result = await comp.activate()
        assert result.success is False
        assert "not installed" in result.message


# ── Lifecycle: deactivate ──────────────────────────────────────────────


class TestDeactivate:
    """CodeGraphComponent.deactivate() is a no-op (CLI binary, no session)."""

    async def test_deactivate_always_succeeds(self):
        comp = CodeGraphComponent(runner=MockRunner())
        result = await comp.deactivate()
        assert result.success is True
        assert "deactivated" in result.message


# ── Lifecycle: uninstall ──────────────────────────────────────────────


class TestUninstall:
    """CodeGraphComponent.uninstall() delegates to npm."""

    async def test_not_installed_returns_success(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "not installed" in result.message

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "uninstalled" in result.message

    async def test_uninstall_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="1.3.1\n"))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )

        async def _run(cmd, *, timeout=None, env=None):
            if cmd[0] == "codegraph":
                return RunResult(returncode=0, stdout="1.3.1\n")
            return RunResult(returncode=1, stderr="permission denied")

        runner.run = _run

        result = await comp.uninstall()
        assert result.success is False
        assert "failed" in result.message


# ── Lifecycle: health ─────────────────────────────────────────────────


class TestHealth:
    """CodeGraphComponent.health() returns a diagnostic dict via status --json."""

    @staticmethod
    def _make_runner(
        status_stdout: str = "",
        status_retcode: int = 0,
        *,
        version: str = "1.3.1\n",
    ) -> MockRunner:
        """Build a runner that returns version output for detect and
        status JSON for the health check."""
        runner = MockRunner()

        async def _run(cmd, *, timeout=None, env=None):
            if "--version" in cmd:
                return RunResult(returncode=0, stdout=version)
            return RunResult(returncode=status_retcode, stdout=status_stdout)

        runner.run = _run
        return runner

    async def test_down_when_not_installed(self, monkeypatch):
        comp = CodeGraphComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: None,
        )
        status = await comp.health()
        assert status["status"] == "down"
        assert status["component"] == "codegraph"
        assert status["version"] is None

    async def test_healthy_via_json(self, monkeypatch):
        """JSON mode: valid JSON → healthy with full diagnostics."""
        status_data = {"version": "1.3.1", "initialized": True, "projectPath": "/repo"}
        runner = self._make_runner(status_stdout=json.dumps(status_data))
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "1.3.1"
        assert status["diagnostics"]["version"] == "1.3.1"
        assert status["diagnostics"]["initialized"] is True

    async def test_json_invalid_falls_back_to_exit_code(self, monkeypatch):
        """JSON mode: invalid JSON with exit 0 → healthy without diagnostics."""
        runner = self._make_runner(status_stdout="not json\n")
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "1.3.1"

    async def test_json_fallback_degraded_on_bad_exit(self, monkeypatch):
        """JSON mode: non-zero exit → degraded with exit code diagnostics."""
        runner = self._make_runner(status_stdout="failed\n", status_retcode=1)
        comp = CodeGraphComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.codegraph.shutil.which",
            lambda cmd: "/usr/local/bin/codegraph",
        )
        status = await comp.health()
        assert status["status"] == "degraded"
        assert status["version"] == "1.3.1"
        assert status["diagnostics"]["status_exit"] == 1
