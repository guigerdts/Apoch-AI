"""Tests for the ``apoch stack`` CLI commands.

Architecture: Thin CLI adapter tests.  All commands are tested with
a mocked ``StackManager`` via ``create_manager`` DI hook.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from apoch.cli import stack as cli_stack
from apoch.stack.component import ComponentInfo, StackComponent
from apoch.stack.descriptor import StackDescriptor
from apoch.stack.manager import StackManager
from apoch.stack.registry import StackRegistry
from apoch.stack.result import OperationResult
from apoch.stack.state import StackState

# ── Runner ───────────────────────────────────────────────────────────
runner = CliRunner()


# ── Mock components ──────────────────────────────────────────────────


class MockCliComponent(StackComponent):
    """Minimal component for CLI tests."""

    def __init__(self, descriptor: StackDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        return ComponentInfo(installed=True, version=self._descriptor.version)

    async def install(self) -> OperationResult:
        return OperationResult(
            success=True,
            component=self._descriptor.name,
            message="installed",
        )

    async def uninstall(self) -> OperationResult:
        return OperationResult(
            success=True,
            component=self._descriptor.name,
            message="uninstalled",
        )

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(
            success=True,
            component=self._descriptor.name,
            message="verified",
        )

    async def activate(self) -> OperationResult:
        return OperationResult(
            success=True,
            component=self._descriptor.name,
            message="activated",
        )

    async def deactivate(self) -> OperationResult:
        return OperationResult(
            success=True,
            component=self._descriptor.name,
            message="deactivated",
        )

    async def health(self) -> dict:
        return {"status": "healthy"}


class NotInstalledComponent(StackComponent):
    """Component whose detect() returns not installed."""

    def __init__(self, descriptor: StackDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        return ComponentInfo(installed=False)

    async def install(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def activate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def deactivate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def health(self) -> dict:
        return {"status": "healthy"}


class OutdatedComponent(StackComponent):
    """Component whose detect() returns an outdated version."""

    def __init__(self, descriptor: StackDescriptor, version: str = "1.0.0") -> None:
        self._descriptor = descriptor
        self._version = version

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        return ComponentInfo(installed=True, version=self._version)

    async def install(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def activate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def deactivate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def health(self) -> dict:
        return {"status": "healthy"}


class ErrorComponent(StackComponent):
    """Component whose detect() raises an exception."""

    def __init__(self, descriptor: StackDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> StackDescriptor:
        return self._descriptor

    async def detect(self) -> ComponentInfo:
        msg = "detect failed"
        raise RuntimeError(msg)

    async def install(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def uninstall(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def verify(self, *, skip_async: bool = False) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def activate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def deactivate(self) -> OperationResult:
        return OperationResult(success=True, component=self._descriptor.name, message="ok")

    async def health(self) -> dict:
        return {"status": "healthy"}


# ── Factory helpers ──────────────────────────────────────────────────


def make_manager() -> StackManager:
    """Create a StackManager with two pre-registered mock components."""
    registry = StackRegistry()
    desc_a = StackDescriptor(
        name="comp-a",
        kind="services",
        version="1.0.0",
        description="Component A",
        entry_point="test:MockCliComponent",
        homepage="https://example.com",
        repository="https://github.com/example/repo",
        docs_url="https://docs.example.com",
        install_command="pip install example",
    )
    desc_b = StackDescriptor(
        name="comp-b",
        kind="integrations",
        version="2.0.0",
        description="Component B",
        entry_point="test:MockCliComponent",
        homepage="https://example.org",
        repository="https://github.com/example/other",
        docs_url="https://docs.example.org",
        install_command="pip install other",
    )
    registry.register(desc_a)
    registry.register(desc_b)
    mgr = StackManager(registry)
    mgr.register_instance("comp-a", MockCliComponent(desc_a))
    mgr.register_instance("comp-b", MockCliComponent(desc_b))
    return mgr


def make_empty_manager() -> StackManager:
    """Create a StackManager with no registered components."""
    registry = StackRegistry()
    return StackManager(registry)


class TestStackCliStatus:
    """apoch stack status."""

    def test_shows_all_components(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout
        assert "comp-b" in result.stdout
        assert "(services)" in result.stdout
        assert "(integrations)" in result.stdout

    def test_shows_installed_state(self, monkeypatch: pytest.MonkeyPatch):
        """Components default to INSTALLED after refresh."""
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert "INSTALLED" in result.stdout

    def test_empty_registry_shows_message(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_empty_manager)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "No stack components registered" in result.stdout


class TestStackCliInstall:
    """apoch stack install."""

    def test_install_all_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["install"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout
        assert "comp-b" in result.stdout
        assert "installed" in result.stdout.lower()

    def test_install_single_component(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["install", "comp-a"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout
        assert "✓" in result.stdout

    def test_install_empty_registry(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_empty_manager)
        result = runner.invoke(cli_stack.cli_app, ["install"])
        assert result.exit_code == 0
        assert "No components to install" in result.stdout


class TestStackCliUninstall:
    """apoch stack uninstall."""

    def test_uninstall_all_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["uninstall"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout
        assert "comp-b" in result.stdout

    def test_uninstall_single(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["uninstall", "comp-b"])
        assert result.exit_code == 0
        assert "comp-b" in result.stdout

    def test_uninstall_empty_registry(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_empty_manager)
        result = runner.invoke(cli_stack.cli_app, ["uninstall"])
        assert result.exit_code == 0
        assert "No components to uninstall" in result.stdout


class TestStackCliVerify:
    """apoch stack verify."""

    def test_verify_default_no_skip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["verify"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout
        assert "comp-b" in result.stdout

    def test_verify_with_skip_async(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["verify", "--skip-async"])
        assert result.exit_code == 0

    def test_verify_single_component(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["verify", "comp-a"])
        assert result.exit_code == 0
        assert "comp-a" in result.stdout

    def test_verify_empty_registry(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_stack, "create_manager", make_empty_manager)
        result = runner.invoke(cli_stack.cli_app, ["verify"])
        assert result.exit_code == 0
        assert "No components to verify" in result.stdout


class TestStackCliErrors:
    """Error handling in stack CLI."""

    def test_install_failure_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch):
        """A failing component install returns exit code 1."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="failing",
            kind="services",
            version="0.1.0",
            description="Always fails",
            entry_point="test:FailingComponent",
        )
        registry.register(desc)

        class FailingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version=desc.version)

            async def install(self) -> OperationResult:
                return OperationResult(
                    success=False,
                    component="failing",
                    message="installation error",
                )

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("failing", FailingComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["install", "failing"])
        assert result.exit_code == 1
        assert "failing" in result.stdout
        assert "installation error" in result.stdout

    def test_install_mixed_results(self, monkeypatch: pytest.MonkeyPatch):
        """When one component fails and another succeeds, exit code is 1."""
        registry = StackRegistry()
        desc_good = StackDescriptor(
            name="good",
            kind="services",
            version="1.0",
            description="Works",
            entry_point="test:GoodComponent",
        )
        desc_bad = StackDescriptor(
            name="bad",
            kind="services",
            version="1.0",
            description="Fails",
            entry_point="test:BadComponent",
        )
        registry.register(desc_good)
        registry.register(desc_bad)

        class GoodComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_good

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class BadComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_bad

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=False, component="bad", message="failed")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("good", GoodComponent())
        mgr.register_instance("bad", BadComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["install"])
        assert result.exit_code == 1
        assert "good" in result.stdout
        assert "bad: failed" in result.stdout

    def test_unknown_subcommand_shows_help(self, monkeypatch: pytest.MonkeyPatch):
        """An unknown subcommand should show an error and exit non-zero."""
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["unknown"])
        assert result.exit_code != 0


class TestStackCliHelp:
    """apoch stack --help and related."""

    def test_help_shows_commands(self):
        result = runner.invoke(cli_stack.cli_app, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.stdout
        assert "install" in result.stdout
        assert "uninstall" in result.stdout
        assert "verify" in result.stdout


class TestStackCliStatusStates:
    """Status output with mixed component states."""

    def test_status_mixed_states(self, monkeypatch: pytest.MonkeyPatch):
        """INSTALLED, ERROR, NOT_INSTALLED each display correctly."""
        registry = StackRegistry()
        desc_good = StackDescriptor(
            name="good",
            kind="services",
            version="1.0",
            description="Works",
            entry_point="test:Good",
            homepage="https://example.com",
            repository="https://github.com/example/repo",
            docs_url="https://docs.example.com",
        )
        desc_broken = StackDescriptor(
            name="broken",
            kind="integrations",
            version="1.0",
            description="Broken",
            entry_point="test:Broken",
            install_command="pip install broken",
        )
        desc_pending = StackDescriptor(
            name="pending",
            kind="services",
            version="1.0",
            description="Not installed",
            entry_point="test:Pending",
            install_command="pip install pending",
        )
        registry.register(desc_good)
        registry.register(desc_broken)
        registry.register(desc_pending)

        class GoodComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_good

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class ErrorComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_broken

            async def detect(self) -> ComponentInfo:
                msg = "detect crashed"
                raise RuntimeError(msg)

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="broken", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="broken", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="broken", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="broken", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="broken", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class PendingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_pending

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=False)

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="pending", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="pending", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="pending", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="pending", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="pending", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("good", GoodComponent())
        mgr.register_instance("broken", ErrorComponent())
        mgr.register_instance("pending", PendingComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "good" in result.stdout
        assert "broken" in result.stdout
        assert "pending" in result.stdout
        assert "INSTALLED" in result.stdout
        assert "ERROR" in result.stdout
        assert "NOT_INSTALLED" in result.stdout


# ── New format tests (PR5.2) ─────────────────────────────────────────


class TestStackCliStatusLinks:
    """Block format — links display."""

    def test_shows_links(self, monkeypatch: pytest.MonkeyPatch):
        """Homepage, repo, docs visible in status output."""
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "Project:" in result.stdout
        assert "Repository:" in result.stdout
        assert "Docs:" in result.stdout
        assert "https://example.com" in result.stdout
        assert "https://github.com/example/repo" in result.stdout
        assert "https://docs.example.com" in result.stdout

    def test_empty_links_omitted(self, monkeypatch: pytest.MonkeyPatch):
        """Empty descriptor fields produce no Project/Repository/Docs lines."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="minimal",
            kind="services",
            version="1.0.0",
            description="Minimal",
            entry_point="test:Minimal",
        )
        registry.register(desc)

        class MinimalComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="minimal", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("minimal", MinimalComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "Project:" not in result.stdout
        assert "Repository:" not in result.stdout
        assert "Docs:" not in result.stdout


class TestStackCliStatusCommands:
    """Block format — Install/Update commands."""

    def test_install_command_shown_when_not_installed(self, monkeypatch: pytest.MonkeyPatch):
        """NOT_INSTALLED shows Install line."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="ospec",
            kind="integrations",
            version="1.0.0",
            description="OpenSpec",
            entry_point="test:NotInstalled",
            install_command="npm install -g @fission-ai/openspec@latest",
            homepage="https://openspec.dev",
            repository="https://github.com/fission-ai/OpenSpec",
            docs_url="https://openspec.dev/docs",
        )
        registry.register(desc)
        mgr = StackManager(registry)
        mgr.register_instance("ospec", NotInstalledComponent(desc))

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "NOT_INSTALLED" in result.stdout
        assert "Install:" in result.stdout
        assert "npm install -g @fission-ai/openspec@latest" in result.stdout

    def test_update_command_shown_when_outdated(self, monkeypatch: pytest.MonkeyPatch):
        """OUTDATED shows Installed/Required/Update."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="ospec",
            kind="integrations",
            version="1.0.0",
            description="OpenSpec",
            entry_point="test:Outdated",
            install_command="npm install -g @fission-ai/openspec@latest",
            homepage="https://openspec.dev",
            repository="https://github.com/fission-ai/OpenSpec",
            docs_url="https://openspec.dev/docs",
            min_version="2.0.0",
        )
        registry.register(desc)
        mgr = StackManager(registry)
        mgr.register_instance("ospec", OutdatedComponent(desc, version="1.5.0"))

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "OUTDATED" in result.stdout
        assert "Installed:" in result.stdout
        assert "1.5.0" in result.stdout
        assert "Required:" in result.stdout
        assert ">=2.0.0" in result.stdout
        assert "Update:" in result.stdout
        assert "npm install -g @fission-ai/openspec@latest" in result.stdout

    def test_installed_hides_install_command(self, monkeypatch: pytest.MonkeyPatch):
        """INSTALLED does NOT show Install or Update."""
        monkeypatch.setattr(cli_stack, "create_manager", make_manager)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "INSTALLED" in result.stdout
        assert "Install:" not in result.stdout
        assert "Update:" not in result.stdout

    def test_error_state_shows_install_command(self, monkeypatch: pytest.MonkeyPatch):
        """ERROR shows Install line."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="failing",
            kind="services",
            version="1.0.0",
            description="Fails",
            entry_point="test:Failing",
            install_command="pip install failing",
        )
        registry.register(desc)

        class FailingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                msg = "unexpected error"
                raise RuntimeError(msg)

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("failing", FailingComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["status"])
        assert result.exit_code == 0
        assert "ERROR" in result.stdout
        assert "Install:" in result.stdout
        assert "pip install failing" in result.stdout


class TestStackCliUninstallErrors:
    """apoch stack uninstall — failure handling."""

    def test_uninstall_failure_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch):
        """A failing component uninstall returns exit code 1."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="failing",
            kind="services",
            version="0.1.0",
            description="Always fails",
            entry_point="test:FailingComponent",
        )
        registry.register(desc)

        class FailingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version=desc.version)

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=False, component="failing", message="removal error")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("failing", FailingComponent())
        # Mark installed so uninstall proceeds
        mgr._statuses["failing"].state = StackState.INSTALLED

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["uninstall", "failing"])
        assert result.exit_code == 1
        assert "failing" in result.stdout
        assert "removal error" in result.stdout

    def test_uninstall_mixed_results(self, monkeypatch: pytest.MonkeyPatch):
        """When one uninstall fails and another succeeds, exit code is 1."""
        registry = StackRegistry()
        desc_good = StackDescriptor(
            name="good",
            kind="services",
            version="1.0",
            description="Works",
            entry_point="test:Good",
        )
        desc_bad = StackDescriptor(
            name="bad", kind="services", version="1.0", description="Fails", entry_point="test:Bad"
        )
        registry.register(desc_good)
        registry.register(desc_bad)

        class GoodComp(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_good

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="good", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        class BadComp(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc_bad

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version="1.0")

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=False, component="bad", message="removal error")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="bad", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("good", GoodComp())
        mgr.register_instance("bad", BadComp())
        mgr._statuses["good"].state = StackState.INSTALLED
        mgr._statuses["bad"].state = StackState.INSTALLED

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["uninstall"])
        assert result.exit_code == 1
        assert "good: ok" in result.stdout or "good" in result.stdout
        assert "bad: removal error" in result.stdout or "removal error" in result.stdout


class TestStackCliVerifyErrors:
    """apoch stack verify — failure handling."""

    def test_verify_failure_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch):
        """A failing component verify returns exit code 1."""
        registry = StackRegistry()
        desc = StackDescriptor(
            name="failing",
            kind="services",
            version="0.1.0",
            description="Always fails",
            entry_point="test:FailingComponent",
        )
        registry.register(desc)

        class FailingComponent(StackComponent):
            @property
            def descriptor(self) -> StackDescriptor:
                return desc

            async def detect(self) -> ComponentInfo:
                return ComponentInfo(installed=True, version=desc.version)

            async def install(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def uninstall(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def verify(self, *, skip_async: bool = False) -> OperationResult:
                return OperationResult(
                    success=False,
                    component="failing",
                    message="integrity error",
                )

            async def activate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def deactivate(self) -> OperationResult:
                return OperationResult(success=True, component="failing", message="ok")

            async def health(self) -> dict:
                return {"status": "healthy"}

        mgr = StackManager(registry)
        mgr.register_instance("failing", FailingComponent())

        monkeypatch.setattr(cli_stack, "create_manager", lambda: mgr)
        result = runner.invoke(cli_stack.cli_app, ["verify", "failing"])
        assert result.exit_code == 1
        assert "failing" in result.stdout
        assert "integrity error" in result.stdout
