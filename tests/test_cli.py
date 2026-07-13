"""Tests for CLI application (RED phase).

Spec: cli-interface §Subcommand Matrix, §List Modules, §Public Interfaces
Architecture: CLI is a thin presentation layer — no business logic in handlers.
Design: Package Structure (cli/app.py, cli/list.py, cli/status.py)

RED-GREEN-TRIANGULATE phases:
  RED:       Tests 1–5 MUST fail — imported modules do not exist yet.
  GREEN:     After creating CLI modules, all tests MUST pass.
  TRIANG:    Additional edge cases added after GREEN.
"""

from __future__ import annotations

import pytest

# =============================================================================
# PHASE RED — import-level tests guaranteed to fail before CLI modules exist
# =============================================================================


class TestAppImports:
    """Phase RED: These MUST fail until cli/app.py exists."""

    def test_app_module_importable(self) -> None:
        """RED: apoch.cli.app module is importable."""
        import apoch.cli.app  # noqa: F401 — ImportError expected

    def test_app_exposes_typer_instance(self) -> None:
        """RED: apoch.cli.app exposes a typer.Typer app."""
        from apoch.cli.app import app  # noqa: F811 — ImportError expected

        assert app is not None

    def test_list_module_importable(self) -> None:
        """RED: apoch.cli.list module is importable."""
        from apoch.cli.list import cli_app  # noqa: F811 — ImportError expected

        assert cli_app is not None

    def test_status_module_importable(self) -> None:
        """RED: apoch.cli.status module is importable."""
        from apoch.cli.status import (  # noqa: F811 — ImportError expected
            cli_app,
        )

        assert cli_app is not None

    def test_output_format_importable(self) -> None:
        """RED: apoch.cli.output.format_output is importable."""
        from apoch.cli.output import (  # noqa: F811 — ImportError expected
            format_output,
        )

        assert callable(format_output)


# =============================================================================
# PHASE GREEN — behavioral tests (pass only AFTER CLI modules are created)
# =============================================================================


class TestAppHelp:
    """apoch --help and apoch --version."""

    def test_help_exits_zero(self) -> None:
        """--help exits 0 and prints non-empty output."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert result.stdout.strip()

    def test_help_shows_subcommands(self) -> None:
        """--help output mentions 'list' and 'status' subcommands."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        lower = result.stdout.lower()
        assert "list" in lower
        assert "status" in lower

    def test_version_exits_zero(self) -> None:
        """--version exits 0 and prints the apoch version string."""
        from typer.testing import CliRunner

        from apoch import __version__
        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestUnknownCommand:
    """Unknown command handling."""

    def test_unknown_exits_2(self) -> None:
        """apoch <unknown> exits 2 (usage error)."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["nonexistent"])
        assert result.exit_code == 2


class TestListCommand:
    """apoch list — delegates to ModuleRegistry.discover()."""

    def test_list_shows_discovered_modules(self, mocker) -> None:
        """apoch list shows names of discovered modules."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        # Build mock entry points
        mock_ep_a = mocker.Mock()
        mock_ep_a.name = "chronicle"
        mock_ep_a.value = "apoch.modules.chronicle.module:ChronicleModule"
        mock_ep_a.dist = None

        mock_ep_b = mocker.Mock()
        mock_ep_b.name = "vision"
        mock_ep_b.value = "apoch.modules.vision.module:VisionModule"
        mock_ep_b.dist = None

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[mock_ep_a, mock_ep_b],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "chronicle" in result.stdout
        assert "vision" in result.stdout

    def test_list_verbose_shows_entry_points(self, mocker) -> None:
        """apoch list --verbose shows entry point paths."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        mock_ep = mocker.Mock()
        mock_ep.name = "testmod"
        mock_ep.value = "test.module:TestModule"
        mock_ep.dist = None

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[mock_ep],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["list", "--verbose"])
        assert result.exit_code == 0
        assert "test.module:TestModule" in result.stdout

    def test_list_json_format(self, mocker) -> None:
        """apoch list --format json returns parseable JSON."""
        import json

        from typer.testing import CliRunner

        from apoch.cli.app import app

        mock_ep = mocker.Mock()
        mock_ep.name = "chronicle"
        mock_ep.value = "apoch.modules.chronicle.module:ChronicleModule"
        mock_ep.dist = None

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[mock_ep],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert any(d["name"] == "chronicle" for d in data)

    def test_list_mixed_states(self, mocker) -> None:
        """apoch list shows correct status labels for mixed states."""
        from typer.testing import CliRunner

        from apoch.cli.app import app
        from apoch.core.module import Module, ModuleState

        mock_ep_a = mocker.Mock()
        mock_ep_a.name = "running_mod"
        mock_ep_a.value = "test.running:RunningMod"
        mock_ep_a.dist = None

        mock_ep_b = mocker.Mock()
        mock_ep_b.name = "unloaded_mod"
        mock_ep_b.value = "test.unloaded:UnloadedMod"
        mock_ep_b.dist = None

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[mock_ep_a, mock_ep_b],
        )

        # Mock ModuleRegistry.loaded so running_mod shows as RUNNING
        from apoch.core.registry import ModuleRegistry

        def patched_load(self, name: str) -> Module:
            mod = mocker.Mock(spec=Module)
            mod.state = ModuleState.RUNNING
            mod.name = name
            self._loaded[name] = mod
            self._init_order.append(name)
            return mod

        mocker.patch.object(ModuleRegistry, "load", patched_load)

        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "running_mod" in result.stdout
        assert "unloaded_mod" in result.stdout


class TestStatusCommand:
    """apoch status — system health and module status."""

    def test_status_exits_zero(self, mocker) -> None:
        """apoch status exits 0."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_status_shows_version(self, mocker) -> None:
        """apoch status output includes the version."""
        from typer.testing import CliRunner

        from apoch import __version__
        from apoch.cli.app import app

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["status"])
        assert __version__ in result.stdout

    def test_status_shows_module_count(self, mocker) -> None:
        """apoch status shows count of discovered modules."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        mock_ep = mocker.Mock()
        mock_ep.name = "chronicle"
        mock_ep.value = "apoch.modules.chronicle.module:ChronicleModule"
        mock_ep.dist = None

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[mock_ep],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["status"])
        assert "1" in result.stdout, f"Expected module count in status output, got: {result.stdout}"

    def test_status_json_format(self, mocker) -> None:
        """apoch status --format json returns parseable JSON."""
        import json

        from typer.testing import CliRunner

        from apoch.cli.app import app

        mocker.patch(
            "apoch.core.registry.entry_points",
            return_value=[],
        )

        runner = CliRunner()
        result = runner.invoke(app, ["status", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "version" in data


class TestOutputFormatter:
    """Output formatter (format_output) for text and JSON modes."""

    def test_format_text_list_of_dicts(self) -> None:
        """format_output with text mode returns formatted text."""
        from apoch.cli.output import format_output

        data = [
            {"name": "chronicle", "version": "0.1.0", "status": "running"},
        ]
        result = format_output(data, output_format="text")
        assert "chronicle" in result
        assert "0.1.0" in result
        assert "running" in result

    def test_format_text_dict(self) -> None:
        """format_output formats a single dict as key-value lines."""
        from apoch.cli.output import format_output

        data = {"version": "0.1.0", "modules": 3}
        result = format_output(data, output_format="text")
        assert "version:" in result
        assert "0.1.0" in result
        assert "modules:" in result
        assert "3" in result

    def test_format_json(self) -> None:
        """format_output with json mode returns JSON."""
        import json

        from apoch.cli.output import format_output

        data = [{"name": "chronicle"}]
        result = format_output(data, output_format="json")
        parsed = json.loads(result)
        assert parsed == data

    def test_format_verbose_adds_detail(self) -> None:
        """format_output with verbose=True includes extra fields."""
        from apoch.cli.output import format_output

        data = [
            {
                "name": "chronicle",
                "version": "0.1.0",
                "status": "running",
                "entry_point": "apoch.modules.chronicle",
                "description": "Test module",
            },
        ]
        result = format_output(data, output_format="text", verbose=True)
        assert "Entry:" in result
        assert "apoch.modules.chronicle" in result
        assert "Desc:" in result
        assert "Test module" in result


class TestAppSubcommandModules:
    """Each command module exposes a typer.Typer() instance named cli_app."""

    def test_list_module_has_cli_app(self) -> None:
        """apoch.cli.list has a cli_app attribute that is a typer.Typer."""
        from typer import Typer

        from apoch.cli.list import cli_app

        assert isinstance(cli_app, Typer)

    def test_status_module_has_cli_app(self) -> None:
        """apoch.cli.status has a cli_app attribute that is a typer.Typer."""
        from typer import Typer

        from apoch.cli.status import cli_app

        assert isinstance(cli_app, Typer)


class TestAppImportableViaName:
    """The app can be imported via the `from apoch.cli.app import app` path."""

    def test_app_is_typer_instance(self) -> None:
        """app is a typer.Typer instance."""
        from typer import Typer

        from apoch.cli.app import app

        assert isinstance(app, Typer)


class TestEntryPointFunction:
    """The entry_point() wrapper handles errors correctly."""

    def test_entry_point_is_callable(self) -> None:
        """entry_point() is a callable function."""
        from apoch.cli.app import entry_point

        assert callable(entry_point)


class TestAppDynamicSubcommands:
    """Dynamic discovery of command modules via entry points."""

    def test_discover_registers_entry_point_command(self, mocker) -> None:
        """discover_and_register loads and registers subcommands from apoch.cli group."""
        import typer
        from typer import Typer
        from typer.testing import CliRunner

        from apoch.cli import discover_and_register

        mock_sub_app = Typer()

        @mock_sub_app.callback(invoke_without_command=True)
        def my_cmd():
            typer.echo("hello from dynamic plugin command")

        mock_ep = mocker.Mock()
        mock_ep.name = "dynamiccmd"
        mock_ep.load.return_value = mock_sub_app

        mocker.patch(
            "importlib.metadata.entry_points",
            return_value=[mock_ep],
        )

        main_app = Typer()
        discover_and_register(main_app)

        runner = CliRunner()
        result = runner.invoke(main_app, ["dynamiccmd"])
        assert result.exit_code == 0
        assert "hello from dynamic plugin command" in result.stdout


class TestEntryPointErrorHandling:
    """The entry_point() wrapper catches ApochError and exits cleanly."""

    def test_entry_point_catches_apoch_error(self, mocker) -> None:
        """entry_point() prints ApochError and exits with 1 without traceback."""
        from apoch.cli.app import entry_point
        from apoch.core.exceptions import ApochError

        # Mock app invocation to raise ApochError
        mocker.patch("apoch.cli.app.app", side_effect=ApochError("Mocked configuration error"))
        mock_echo = mocker.patch("typer.echo")

        with pytest.raises(SystemExit) as excinfo:
            entry_point()

        assert excinfo.value.code == 1
        mock_echo.assert_any_call("Error: Mocked configuration error", err=True)

    def test_entry_point_catches_generic_error(self, mocker) -> None:
        """entry_point() prints unexpected error and exits with 1."""
        from apoch.cli.app import entry_point

        mocker.patch("apoch.cli.app.app", side_effect=ValueError("Unexpected crash"))
        mock_echo = mocker.patch("typer.echo")

        with pytest.raises(SystemExit) as excinfo:
            entry_point()

        assert excinfo.value.code == 1
        mock_echo.assert_any_call("Unexpected error: Unexpected crash", err=True)
