"""Tests for the Engram Stack Component.

PR6.1 — Foundation: ENGRA_DESCRIPTOR, parse_engram_version, and
entry-point resolution.

PR6.2 — Lifecycle: detect, install, uninstall, verify, health,
activate, and deactivate via MockRunner.
"""

from __future__ import annotations

from pathlib import Path

from apoch.stack.components.engram import (
    ENGRA_DESCRIPTOR,
    EngramComponent,
    _get_install_args,
    _get_uninstall_args,
    parse_engram_version,
)
from apoch.stack.runner import MockRunner, RunResult

# ── Foundation: Descriptor ────────────────────────────────────────────


class TestDescriptor:
    """ENGRA_DESCRIPTOR contains factual metadata about the official project."""

    def test_id(self):
        assert ENGRA_DESCRIPTOR.id == "engram"

    def test_name(self):
        assert ENGRA_DESCRIPTOR.name == "Engram"

    def test_kind(self):
        assert ENGRA_DESCRIPTOR.kind == "integrations"

    def test_install_command(self):
        assert "brew install" in ENGRA_DESCRIPTOR.install_command

    def test_homepage(self):
        assert "github.com/Gentleman-Programming/engram" in ENGRA_DESCRIPTOR.homepage

    def test_repository(self):
        assert "github.com/Gentleman-Programming/engram" in ENGRA_DESCRIPTOR.repository

    def test_requires_empty(self):
        assert ENGRA_DESCRIPTOR.requires == ()

    def test_capabilities(self):
        assert "memory" in ENGRA_DESCRIPTOR.capabilities
        assert "mcp" in ENGRA_DESCRIPTOR.capabilities
        assert "search" in ENGRA_DESCRIPTOR.capabilities


# ── Foundation: Version parser ────────────────────────────────────────


class TestParseVersion:
    """parse_engram_version handles multiple output formats."""

    def test_engram_prefix(self):
        assert parse_engram_version("engram 1.19.0") == "1.19.0"

    def test_v_prefix(self):
        assert parse_engram_version("v1.19.0") == "1.19.0"

    def test_bare(self):
        assert parse_engram_version("1.19.0") == "1.19.0"

    def test_multiline(self):
        assert parse_engram_version("foo\nengram 1.19.0\nbar") == "1.19.0"

    def test_nonsense(self):
        assert parse_engram_version("not-a-version") is None

    def test_empty(self):
        assert parse_engram_version("") is None


# ── Foundation: Component instantiation ───────────────────────────────


class TestComponent:
    """EngramComponent can be instantiated and has correct descriptor."""

    def test_descriptor_is_descriptor(self):
        comp = EngramComponent()
        assert comp.descriptor is ENGRA_DESCRIPTOR

    def test_default_runner_is_real_runner(self):
        comp = EngramComponent()
        from apoch.stack.runner import RealRunner

        assert isinstance(comp._runner, RealRunner)

    def test_custom_runner_injected(self):
        runner = MockRunner()
        comp = EngramComponent(runner=runner)
        assert comp._runner is runner


# ── Foundation: Entry point ───────────────────────────────────────────


class TestEntryPoint:
    """The entry point resolves correctly via importlib.metadata."""

    def test_entry_point_resolves(self):
        from importlib.metadata import entry_points

        eps = entry_points(group="apoch.stack.components")
        engram_eps = [ep for ep in eps if ep.name == "engram"]
        assert len(engram_eps) == 1
        ep = engram_eps[0]
        assert ep.value == "apoch.stack.components.engram:EngramComponent"


# ── Helpers ───────────────────────────────────────────────────────────


class TestGetInstallArgs:
    """_get_install_args is platform-aware."""

    def test_darwin_returns_brew(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Darwin")
        args = _get_install_args()
        assert args == ["brew", "install", "gentleman-programming/tap/engram"]

    def test_linux_returns_brew(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Linux")
        args = _get_install_args()
        assert args == ["brew", "install", "gentleman-programming/tap/engram"]

    def test_windows_returns_go_install(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Windows")
        args = _get_install_args()
        assert args == [
            "go", "install",
            "github.com/Gentleman-Programming/engram/cmd/engram@latest",
        ]

    def test_unknown_os_falls_back_to_brew(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "FreeBSD")
        args = _get_install_args()
        assert args == ["brew", "install", "gentleman-programming/tap/engram"]


class TestGetUninstallArgs:
    """_get_uninstall_args is path-aware and platform-aware."""

    def test_homebrew_path_darwin(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Darwin")
        args = _get_uninstall_args(Path("/usr/local/bin/engram"))
        assert args == ["brew", "uninstall", "engram"]

    def test_homebrew_path_linux(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Linux")
        args = _get_uninstall_args(Path("/home/linuxbrew/.linuxbrew/bin/engram"))
        assert args == ["brew", "uninstall", "engram"]

    def test_windows_path(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Windows")
        args = _get_uninstall_args(Path("C:\\go\\bin\\engram.exe"))
        assert args == [
            "go", "clean", "-i",
            "github.com/Gentleman-Programming/engram/cmd/engram",
        ]

    def test_unknown_detection_returns_none(self, monkeypatch):
        monkeypatch.setattr("apoch.stack.components.engram.platform.system", lambda: "Linux")
        args = _get_uninstall_args(Path("/custom/bin/engram"))
        assert args is None

    def test_none_path_returns_none(self):
        assert _get_uninstall_args(None) is None


# ── Lifecycle: detect ─────────────────────────────────────────────────


class TestDetect:
    """EngramComponent.detect() observes the local system."""

    async def test_not_installed_when_binary_missing(self, monkeypatch):
        comp = EngramComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        info = await comp.detect()
        assert info.installed is False

    async def test_installed_when_binary_found(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version == "1.19.0"
        assert info.executable_path == Path("/usr/local/bin/engram")

    async def test_detect_fails_when_version_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="error"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        info = await comp.detect()
        assert info.installed is False
        assert "version check failed" in (info.metadata.get("error") or "")

    async def test_unparseable_version_returns_none(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="Engram Daily Build\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        info = await comp.detect()
        assert info.installed is True
        assert info.version is None
        assert info.executable_path == Path("/usr/local/bin/engram")


# ── Lifecycle: install ────────────────────────────────────────────────


class TestInstall:
    """EngramComponent.install() delegates to the platform installer."""

    async def test_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        result = await comp.install()
        assert result.success is True
        assert result.component == "engram"
        assert "installed" in result.message

    async def test_install_command_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=1, stderr="brew: command not found"))
        comp = EngramComponent(runner=runner)
        result = await comp.install()
        assert result.success is False
        assert "failed" in result.message

    async def test_install_succeeds_but_binary_not_found(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        result = await comp.install()
        assert result.success is False
        assert "binary not found" in result.message


# ── Lifecycle: uninstall ──────────────────────────────────────────────


class TestUninstall:
    """EngramComponent.uninstall() delegates to the platform uninstaller."""

    async def test_not_installed(self, monkeypatch):
        comp = EngramComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        result = await comp.uninstall()
        assert result.success is False
        assert "not installed" in result.message

    async def test_homebrew_uninstall_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        # First call to run() is for detect (version check),
        # second is for the uninstall command
        result = await comp.uninstall()
        assert result.success is True
        assert "uninstalled" in result.message

    async def test_uninstall_command_fails(self, monkeypatch):
        """Uninstall fails when the package-manager command returns non-zero."""
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )

        # Override run so detect succeeds but uninstall fails
        async def _run(cmd, *, timeout=None, env=None):
            if cmd == ["engram", "version"]:
                return RunResult(returncode=0, stdout="engram 1.19.0\n")
            return RunResult(returncode=1, stderr="permission denied")

        runner.run = _run

        result = await comp.uninstall()
        assert result.success is False
        assert "failed" in result.message

    async def test_manual_removal_needed(self, monkeypatch):
        """When the binary path is not package-managed, suggest manual removal."""
        runner = MockRunner(result=RunResult(returncode=0))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/opt/custom/bin/engram",
        )
        result = await comp.uninstall()
        assert result.success is False
        assert "manually" in result.message


# ── Lifecycle: verify ─────────────────────────────────────────────────


class TestVerify:
    """EngramComponent.verify() validates the installation."""

    async def test_not_installed(self, monkeypatch):
        comp = EngramComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        result = await comp.verify()
        assert result.success is False
        assert "not installed" in result.message

    async def test_verify_success(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        result = await comp.verify()
        assert result.success is True
        assert "verified" in result.message

    async def test_doctor_fails(self, monkeypatch):
        """Return doctor failure exit code properly."""
        # detect() needs returncode=0, verify's doctor call needs returncode != 0
        # With MockRunner we only get one result, so we simulate by patching
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )

        # After detect succeeds, mock the doctor call to fail
        async def _fail_on_doctor(cmd, *, timeout=None, env=None):
            if "doctor" in cmd:
                return RunResult(returncode=1, stderr="doctor failed")
            return RunResult(returncode=0, stdout="engram 1.19.0\n")

        runner.run = _fail_on_doctor

        result = await comp.verify()
        assert result.success is False
        assert "doctor failed" in result.message

    async def test_skip_async_still_runs_doctor(self, monkeypatch):
        """skip_async flag does not skip the local doctor check."""
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        result = await comp.verify(skip_async=True)
        assert result.success is True
        assert "verified" in result.message


# ── Lifecycle: health ─────────────────────────────────────────────────


class TestHealth:
    """EngramComponent.health() returns a diagnostic dict."""

    async def test_down_when_not_installed(self, monkeypatch):
        comp = EngramComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        status = await comp.health()
        assert status["status"] == "down"
        assert status["component"] == "engram"

    async def test_healthy_when_doctor_passes(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        status = await comp.health()
        assert status["status"] == "healthy"
        assert status["version"] == "1.19.0"

    async def test_degraded_when_doctor_fails(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )

        async def _fail_doctor(cmd, *, timeout=None, env=None):
            if "doctor" in cmd:
                return RunResult(returncode=1, stderr="not healthy")
            return RunResult(returncode=0, stdout="engram 1.19.0\n")

        runner.run = _fail_doctor

        status = await comp.health()
        assert status["status"] == "degraded"
        assert status["diagnostics"]["doctor_exit"] == 1


# ── Lifecycle: activate / deactivate ──────────────────────────────────


class TestActivate:
    """EngramComponent.activate() verifies the binary is operational."""

    async def test_activate_when_installed(self, monkeypatch):
        runner = MockRunner(result=RunResult(returncode=0, stdout="engram 1.19.0\n"))
        comp = EngramComponent(runner=runner)
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: "/usr/local/bin/engram",
        )
        result = await comp.activate()
        assert result.success is True
        assert "active" in result.message

    async def test_activate_fails_when_not_installed(self, monkeypatch):
        comp = EngramComponent(runner=MockRunner())
        monkeypatch.setattr(
            "apoch.stack.components.engram.shutil.which",
            lambda cmd: None,
        )
        result = await comp.activate()
        assert result.success is False
        assert "not installed" in result.message


class TestDeactivate:
    """EngramComponent.deactivate() is a no-op (CLI binary, no session)."""

    async def test_deactivate_always_succeeds(self):
        comp = EngramComponent(runner=MockRunner())
        result = await comp.deactivate()
        assert result.success is True
        assert "deactivated" in result.message
