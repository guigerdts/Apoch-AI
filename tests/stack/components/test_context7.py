"""Tests for the Context7 Stack Component.

PR7.1 — Foundation: DESCRIPTOR, _parse_version, and entry-point resolution.
PR7.2 — Lifecycle: install, uninstall, verify, health, activate, and
        deactivate via MockRunner.
"""

from __future__ import annotations

from pathlib import Path

from apoch.stack.components.context7 import (
    CONTEXT7_DESCRIPTOR,
    Context7Component,
    _parse_version,
)
from apoch.stack.runner import MockRunner, RunResult

# ── Foundation: Descriptor ────────────────────────────────────────────


class TestDescriptor:
    """CONTEXT7_DESCRIPTOR contains factual metadata about the official project."""

    def test_id(self):
        assert CONTEXT7_DESCRIPTOR.id == "context7"

    def test_name(self):
        assert CONTEXT7_DESCRIPTOR.name == "Context7"

    def test_kind(self):
        assert CONTEXT7_DESCRIPTOR.kind == "integrations"

    def test_install_command(self):
        assert "npm install -g" in CONTEXT7_DESCRIPTOR.install_command

    def test_homepage(self):
        assert CONTEXT7_DESCRIPTOR.homepage == "https://context7.com"

    def test_repository(self):
        assert "github.com/upstash/context7" in CONTEXT7_DESCRIPTOR.repository

    def test_requires_node(self):
        assert "node" in CONTEXT7_DESCRIPTOR.requires[0]


# ── Foundation: Version parser ────────────────────────────────────────


class TestParseVersion:
    """_parse_version handles multiple output formats."""

    def test_ctx7_prefix(self):
        assert _parse_version("ctx7 0.5.4") == "0.5.4"

    def test_v_prefix(self):
        assert _parse_version("v0.5.4") == "0.5.4"

    def test_bare(self):
        assert _parse_version("0.5.4") == "0.5.4"

    def test_multiline(self):
        assert _parse_version("foo\nctx7 0.5.4\nbar") == "0.5.4"

    def test_nonsense(self):
        assert _parse_version("not-a-version") is None

    def test_empty(self):
        assert _parse_version("") is None


# ── Foundation: Component instantiation ───────────────────────────────


class TestComponent:
    """Context7Component can be instantiated and has correct descriptor."""

    def test_descriptor_is_descriptor(self):
        comp = Context7Component()
        assert comp.descriptor is CONTEXT7_DESCRIPTOR

    def test_default_runner_is_real_runner(self):
        comp = Context7Component()
        from apoch.stack.runner import RealRunner

        assert isinstance(comp._runner, RealRunner)

    def test_custom_runner_injected(self):
        runner = MockRunner()
        comp = Context7Component(runner=runner)
        assert comp._runner is runner


# ── Foundation: Entry point ───────────────────────────────────────────


class TestEntryPoint:
    """The entry point resolves correctly via importlib.metadata."""

    def test_entry_point_resolves(self):
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.stack.components")
        context7_eps = [ep for ep in eps if ep.name == "context7"]
        assert len(context7_eps) == 1
        ep = context7_eps[0]
        assert ep.value == "apoch.stack.components.context7:Context7Component"


# ── Lifecycle: detect ─────────────────────────────────────────────────


class TestDetect:
    """Context7Component.detect() observes the local system."""

    async def test_not_installed_when_binary_missing(self, monkeypatch):
        comp = Context7Component(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        info = await comp.detect()
        assert info.installed is False

    async def test_installed_when_binary_found(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version == "0.5.4"
        assert info.executable_path == Path("/usr/local/bin/ctx7")

    async def test_detect_fails_when_version_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="error"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        info = await comp.detect()
        assert info.installed is False
        assert "version check failed" in (info.metadata.get("error") or "")

    async def test_unparseable_version_returns_none(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="Context7 Nightly\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version is None
        assert info.executable_path == Path("/usr/local/bin/ctx7")


# ── Lifecycle: install ────────────────────────────────────────────────


class TestInstall:
    """Context7Component.install() delegates to npm."""

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        result = await comp.install()
        assert result.success is True
        assert result.component == "context7"
        assert "installed" in result.message

    async def test_install_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="npm ERR!"))
        comp = Context7Component(runner=runner)
        result = await comp.install()
        assert result.success is False
        assert "failed" in result.message

    async def test_binary_not_found_after_install(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        result = await comp.install()
        assert result.success is False
        assert "binary not found" in result.message


# ── Lifecycle: uninstall ──────────────────────────────────────────────


class TestUninstall:
    """Context7Component.uninstall() delegates to npm."""

    async def test_not_installed_returns_success(self, monkeypatch):
        comp = Context7Component(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "not installed" in result.message

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        result = await comp.uninstall()
        assert result.success is True
        assert "uninstalled" in result.message

    async def test_uninstall_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )

        async def _run(cmd, *, timeout=None, env=None):
            if cmd[0] == "ctx7":
                return RunResult(returncode=0, stdout="0.5.4\n")
            return RunResult(returncode=1, stderr="permission denied")

        runner.run = _run

        result = await comp.uninstall()
        assert result.success is False
        assert "failed" in result.message


# ── Lifecycle: verify ─────────────────────────────────────────────────


class TestVerify:
    """Context7Component.verify() validates the installation."""

    async def test_not_installed(self, monkeypatch):
        comp = Context7Component(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        result = await comp.verify()
        assert result.success is False
        assert "not installed" in result.message

    async def test_verify_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        result = await comp.verify()
        assert result.success is True
        assert "verified" in result.message

    async def test_help_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )

        async def _fail_help(cmd, *, timeout=None, env=None):
            if "--help" in cmd:
                return RunResult(returncode=1, stderr="help failed")
            return RunResult(returncode=0, stdout="0.5.4\n")

        runner.run = _fail_help

        result = await comp.verify()
        assert result.success is False
        assert "help failed" in result.message


# ── Lifecycle: health ─────────────────────────────────────────────────


class TestHealth:
    """Context7Component.health() returns a diagnostic dict."""

    async def test_down_when_not_installed(self, monkeypatch):
        comp = Context7Component(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        status = await comp.health()
        assert status["status"] == "down"
        assert status["component"] == "context7"
        assert status["version"] is None

    async def test_healthy_when_installed_and_version_parsed(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "0.5.4"
        assert status["component"] == "context7"

    async def test_degraded_when_version_unparseable(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="Context7 Nightly\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        status = await comp.health()
        assert status["status"] == "degraded"
        assert status["version"] is None
        assert "version could not be parsed" in status["diagnostics"]["error"]


# ── Lifecycle: activate / deactivate ──────────────────────────────────


class TestActivate:
    """Context7Component.activate() verifies the binary is operational."""

    async def test_activate_when_installed(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="0.5.4\n"))
        comp = Context7Component(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: "/usr/local/bin/ctx7",
        )
        result = await comp.activate()
        assert result.success is True
        assert "active" in result.message

    async def test_activate_fails_when_not_installed(self, monkeypatch):
        comp = Context7Component(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.context7.shutil.which",
            lambda cmd: None,
        )
        result = await comp.activate()
        assert result.success is False
        assert "not installed" in result.message


class TestDeactivate:
    """Context7Component.deactivate() is a no-op (CLI binary, no session)."""

    async def test_deactivate_always_succeeds(self):
        comp = Context7Component(runner=MockRunner())
        result = await comp.deactivate()
        assert result.success is True
        assert "deactivated" in result.message
