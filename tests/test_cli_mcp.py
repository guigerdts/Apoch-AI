"""Tests for CLI mcp command (RED phase).

Spec: agent-adapter §Gateway Health
Architecture: CLI delegates to adapter.start/stop — no direct OpenCodeAdapter usage.
"""

from __future__ import annotations


class TestMcpCommand:
    """apoch mcp command — start, stop, restart."""

    def test_mcp_module_importable(self) -> None:
        """cli.mcp module is importable."""
        import apoch.cli.mcp  # noqa: F401

    def test_mcp_has_cli_app(self) -> None:
        """cli.mcp has a cli_app typer.Typer instance."""
        from typer import Typer

        from apoch.cli.mcp import cli_app

        assert isinstance(cli_app, Typer)

    def test_mcp_shows_help(self) -> None:
        """apoch mcp --help exits 0."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0
