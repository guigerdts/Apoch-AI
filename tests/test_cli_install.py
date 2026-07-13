"""Tests for CLI install command.

Spec: cli-interface §Install Module
Architecture: CLI delegates to adapter — no direct OpenCodeConfig usage.
"""

from __future__ import annotations


class TestInstallCommand:
    """apoch install command — delegation only."""

    def test_install_module_importable(self) -> None:
        """cli.install module is importable."""
        import apoch.cli.install  # noqa: F401

    def test_install_has_cli_app(self) -> None:
        """cli.install has a cli_app typer.Typer instance."""
        from typer import Typer

        from apoch.cli.install import cli_app

        assert isinstance(cli_app, Typer)

    def test_install_shows_help(self) -> None:
        """apoch install --help exits 0."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0


class TestUninstallCommand:
    """apoch uninstall command — delegation only."""

    def test_uninstall_module_importable(self) -> None:
        """cli.uninstall module is importable."""
        import apoch.cli.uninstall  # noqa: F401

    def test_uninstall_has_cli_app(self) -> None:
        """cli.uninstall has a cli_app typer.Typer instance."""
        from typer import Typer

        from apoch.cli.uninstall import cli_app

        assert isinstance(cli_app, Typer)

    def test_uninstall_shows_help(self) -> None:
        """apoch uninstall --help exits 0."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
