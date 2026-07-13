"""Tests for CLI doctor command (RED phase).

Spec: cli-interface §Doctor Diagnostics
Architecture: Doctor iterates over all registered adapters.
"""

from __future__ import annotations


class TestDoctorCommand:
    """apoch doctor command — diagnostics for all adapters."""

    def test_doctor_module_importable(self) -> None:
        """cli.doctor module is importable."""
        import apoch.cli.doctor  # noqa: F401

    def test_doctor_has_cli_app(self) -> None:
        """cli.doctor has a cli_app typer.Typer instance."""
        from typer import Typer

        from apoch.cli.doctor import cli_app

        assert isinstance(cli_app, Typer)

    def test_doctor_shows_help(self) -> None:
        """apoch doctor --help exits 0."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
