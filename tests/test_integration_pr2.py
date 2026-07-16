"""PR2 Integration Tests — Bloques A–E end-to-end validation.

Spec: agent-adapter, cli-interface
Architecture: Validates the full CLI → Registry → Adapter → Config chain
without mocking.  Each test exercises the real code path with an isolated
filesystem (tmp_path).

Design principles:
- No mocks for the code under test (real adapter, real config, real registry)
- No sleeps, no network access, no state sharing between tests
- Each test is self-contained with tmp_path isolation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# =========================================================================
# A. Full CLI → Registry → Adapter → Config chain
# =========================================================================


class TestInstallEndToEnd:
    """apoch install — full end-to-end flow."""

    def test_install_creates_backup_and_writes_config(self, tmp_path: Path, monkeypatch) -> None:
        """apoch install backs up, computes diff, and writes config."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        # Create an existing opencode.json with a non-Apoch tool (at root level)
        config_path = tmp_path / "opencode.json"
        config_path.write_text(
            json.dumps({"mcp": {"existing-tool": {"command": "tool", "args": []}}})
        )

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # Simulate user saying "yes" to the consent prompt
        result = runner.invoke(app, ["install"], input="y\n")

        assert result.exit_code == 0, f"install failed: {result.output}"
        assert "Apoch-AI installed" in result.output or "already installed" in result.output

        # Verify backup was created
        backup_dir = tmp_path / ".apoch-backups"
        backups = list(backup_dir.glob("opencode-*.json"))
        assert len(backups) >= 1, "No backup file was created"

        # Verify the apoch entry was written
        written = json.loads(config_path.read_text())
        assert "apoch" in written["mcp"]
        assert written["mcp"]["apoch"]["command"] == ["apoch", "mcp", "serve"]

    def test_install_idempotent_when_already_installed(self, tmp_path: Path, monkeypatch) -> None:
        """apoch install is idempotent — reports already installed."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        config_path = tmp_path / "opencode.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcp": {
                        "apoch": {
                            "command": ["apoch", "mcp", "serve"],
                            "type": "local",
                        },
                    }
                }
            )
        )

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # First install — already installed
        result = runner.invoke(app, ["install"], input="y\n")

        assert result.exit_code == 0
        assert "already installed" in result.output

        # Backup was cleaned up by discard_install (no changes needed)
        backup_dir = tmp_path / ".apoch-backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("opencode-*.json"))
            assert len(backups) == 0  # discarded because already installed

    def test_install_cancelled_when_user_declines(self, tmp_path: Path, monkeypatch) -> None:
        """apoch install cancels when user says no — no config written."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        config_path = tmp_path / "opencode.json"
        original = json.dumps({"key": "value"})
        config_path.write_text(original)

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # User declines
        result = runner.invoke(app, ["install"], input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.output

        # Config should be unchanged
        assert config_path.read_text() == original

        # Backup should have been cleaned up by discard_install
        backup_dir = tmp_path / ".apoch-backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("opencode-*.json"))
            assert len(backups) == 0  # discard_install removed the backup


# =========================================================================
# C. apoch uninstall — end-to-end
# =========================================================================


class TestUninstallEndToEnd:
    """apoch uninstall — full end-to-end flow."""

    def test_uninstall_restores_config(self, tmp_path: Path, monkeypatch) -> None:
        """apoch uninstall restores opencode.json from backup."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        config_path = tmp_path / "opencode.json"
        config_data = {"mcp": {"apoch": {"command": ["apoch", "mcp", "serve"]}}}
        config_path.write_text(json.dumps(config_data))

        # Create a backup (as install would have done)
        backup_dir = tmp_path / ".apoch-backups"
        backup_dir.mkdir(parents=True)
        original_backup = {"original": "config"}
        backup_path = backup_dir / "opencode-20250101_000000.json"
        backup_path.write_text(json.dumps(original_backup))

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        result = runner.invoke(app, ["uninstall"], input="y\n")

        assert result.exit_code == 0, f"uninstall failed: {result.output}"
        assert "removed" in result.output

        # Config should be restored from backup
        restored = json.loads(config_path.read_text())
        assert restored == original_backup


# =========================================================================
# D. apoch doctor — iterates registry.list_adapters()
# =========================================================================


class TestDoctorEndToEnd:
    """apoch doctor — iterates all registered adapters."""

    def test_doctor_shows_registered_adapters(self) -> None:
        """apoch doctor lists and checks all registered adapters."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])

        # Should exit 0 or 1 depending on health
        # We just verify it runs and mentions "opencode"
        assert "opencode" in result.output

    def test_doctor_does_not_hardcode_adapter_names(self) -> None:
        """Doctor uses registry.list_adapters() — no hardcoded names."""
        import ast
        from pathlib import Path

        doctor_source = Path("src/apoch/cli/doctor.py").read_text()
        tree = ast.parse(doctor_source)

        # Collect all function call names
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)

        # Should NOT call get_adapter("opencode") directly
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get_adapter":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and arg.value in (
                            "opencode",
                            "claude",
                            "gemini",
                            "codex",
                        ):
                            pytest.fail(
                                f"doctor hardcodes adapter name '{arg.value}' — "
                                f"should use registry.list_adapters()"
                            )

    def test_doctor_uses_list_adapters(self) -> None:
        """doctor.py imports and uses list_adapters from registry."""
        import ast
        from pathlib import Path

        doctor_source = Path("src/apoch/cli/doctor.py").read_text()
        tree = ast.parse(doctor_source)

        has_list_adapters = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "list_adapters":
                    has_list_adapters = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "list_adapters":
                    has_list_adapters = True

        assert has_list_adapters, "doctor.py does not call list_adapters()"


# =========================================================================
# E. apoch mcp start/stop — lifecycle management
# =========================================================================


class TestMcpLifecycleEndToEnd:
    """apoch mcp start/stop — full lifecycle validation."""

    def test_mcp_start_stop_lifecycle(self) -> None:
        """apoch mcp start then stop — clean lifecycle."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()

        # Start
        result = runner.invoke(app, ["mcp", "start"])
        assert result.exit_code == 0, f"mcp start failed: {result.output}"
        assert "started" in result.output

        # Start again (idempotence)
        result = runner.invoke(app, ["mcp", "start"])
        assert result.exit_code == 0
        assert "already" not in result.output  # no error

        # Stop
        result = runner.invoke(app, ["mcp", "stop"])
        assert result.exit_code == 0
        assert "stopped" in result.output

        # Stop again (idempotence)
        result = runner.invoke(app, ["mcp", "stop"])
        assert result.exit_code == 0

    def test_mcp_restart(self) -> None:
        """apoch mcp restart works."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["mcp", "restart"])
        assert result.exit_code == 0, f"mcp restart failed: {result.output}"
        assert "restarted" in result.output


# =========================================================================
# B. apoch install data flow — low-level programmatic validation
# =========================================================================


class TestInstallDataFlow:
    """apoch install — programmatic validation without CLI interaction."""

    def test_install_prepare_backup_apply_flow(self, tmp_path: Path, monkeypatch) -> None:
        """Full programmatic flow: prepare → backup → apply → verify."""
        from apoch.adapters.opencode.config import OpenCodeConfig
        from apoch.adapters.opencode.server import OpenCodeAdapter

        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps({"mcp": {"existing": {"command": "old"}}}))

        monkeypatch.chdir(tmp_path)

        adapter = OpenCodeAdapter(config={})

        # 1. Prepare
        plan = adapter.prepare_install()
        assert plan.backup_path.exists()
        assert "existing" in plan.current.get("mcp", {})
        assert "apoch" in plan.proposed.get("mcp", {})

        # 2. Apply
        adapter.apply_install(plan)

        # 3. Verify
        cfg = OpenCodeConfig()
        written = cfg.read()
        assert "apoch" in written.get("mcp", {})
        assert "existing" in written.get("mcp", {})  # preserved
        assert written["mcp"]["apoch"]["command"] == ["apoch", "mcp", "serve"]

    def test_uninstall_restores_original(self, tmp_path: Path, monkeypatch) -> None:
        """Full programmatic flow: install then uninstall restores original."""
        from apoch.adapters.opencode.server import OpenCodeAdapter

        config_path = tmp_path / "opencode.json"
        original = {"key": "original_value"}
        config_path.write_text(json.dumps(original))

        monkeypatch.chdir(tmp_path)

        adapter = OpenCodeAdapter(config={})

        # Install
        plan = adapter.prepare_install()
        assert plan.backup_path.exists()
        adapter.apply_install(plan)

        # Verify installed
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        after_install = cfg.read()
        assert "apoch" in after_install.get("mcp", {})

        # Uninstall — should restore original (before install)
        adapter.uninstall()

        restored = cfg.read()
        assert restored == original


# =========================================================================
# Registry interaction — adapter discovery works
# =========================================================================


class TestRegistryIntegration:
    """Adapter registry works end-to-end through the CLI layer."""

    def test_registry_has_opencode(self) -> None:
        """Registry contains the opencode adapter."""
        from apoch.adapters.registry import list_adapters

        names = list_adapters()
        assert "opencode" in names

    def test_get_adapter_returns_instance(self) -> None:
        """get_adapter returns a working OpenCodeAdapter instance."""
        from apoch.adapters.registry import get_adapter

        adapter = get_adapter("opencode")
        from apoch.adapters.opencode.server import OpenCodeAdapter

        assert isinstance(adapter, OpenCodeAdapter)

    def test_cli_list_shows_adapters(self) -> None:
        """apoch list shows adapter info via the CLI."""
        from typer.testing import CliRunner

        from apoch.cli.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
