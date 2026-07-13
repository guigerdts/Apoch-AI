"""Tests for OpenCodeAdapter install/uninstall lifecycle.

Spec: cli-interface §Install Module, §Uninstall
Architecture: Verifies that the adapter owns all OpenCodeConfig
interaction — CLI never imports it.
"""

from __future__ import annotations

import json


def _with_config(tmp_path, monkeypatch) -> None:
    """Create an isolated opencode.json and chdir to tmp_path."""
    opencode_path = tmp_path / ".opencode" / "opencode.json"
    opencode_path.parent.mkdir(parents=True)
    opencode_path.write_text("{}")
    monkeypatch.chdir(tmp_path)


class TestPrepareInstall:
    """OpenCodeAdapter.prepare_install() behavior."""

    def test_prepare_install_returns_install_plan(self, tmp_path, monkeypatch) -> None:
        """prepare_install() returns an InstallPlan with backup + proposed."""
        _with_config(tmp_path, monkeypatch)
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={})
        plan = adapter.prepare_install()

        assert plan.backup_path is not None
        assert isinstance(plan.current, dict)
        assert isinstance(plan.proposed, dict)
        assert "mcpServers" in plan.proposed
        assert "apoch" in plan.proposed["mcpServers"]

    def test_prepare_install_creates_backup_file(self, tmp_path, monkeypatch) -> None:
        """prepare_install() writes a backup file on disk."""
        _with_config(tmp_path, monkeypatch)
        from apoch.adapters.opencode.server import OpenCodeAdapter

        adapter = OpenCodeAdapter(config={})
        plan = adapter.prepare_install()
        assert plan.backup_path.exists()

    def test_prepare_install_preserves_existing_config(self, tmp_path, monkeypatch) -> None:
        """prepare_install() preserves existing MCP servers in proposed."""
        from apoch.adapters.opencode.server import OpenCodeAdapter

        # Write an existing opencode.json with a non-Apoch entry
        existing = {
            "mcpServers": {
                "some-tool": {"command": "tool", "args": []},
            },
        }
        opencode_path = tmp_path / ".opencode" / "opencode.json"
        opencode_path.parent.mkdir(parents=True)
        opencode_path.write_text(json.dumps(existing))
        monkeypatch.chdir(tmp_path)

        adapter = OpenCodeAdapter(config={})
        plan = adapter.prepare_install()

        assert "some-tool" in plan.proposed["mcpServers"]
        assert "apoch" in plan.proposed["mcpServers"]
        assert plan.current == existing


class TestApplyInstall:
    """OpenCodeAdapter.apply_install() behavior."""

    def test_apply_install_writes_config(self, tmp_path, monkeypatch) -> None:
        """apply_install() persists the proposed config to disk."""
        from apoch.adapters.opencode.server import InstallPlan, OpenCodeAdapter

        opencode_path = tmp_path / ".opencode" / "opencode.json"
        opencode_path.parent.mkdir(parents=True)
        opencode_path.write_text("{}")  # Must exist for _path_from_cwd to find it
        monkeypatch.chdir(tmp_path)

        backup_path = tmp_path / "backup.json"
        backup_path.write_text("{}")
        plan = InstallPlan(
            backup_path=backup_path,
            current={},
            proposed={"mcpServers": {"apoch": {"command": "apoch", "args": ["mcp"]}}},
        )
        adapter = OpenCodeAdapter(config={})
        adapter.apply_install(plan)

        written = json.loads(opencode_path.read_text())
        assert "apoch" in written["mcpServers"]
        assert written["mcpServers"]["apoch"]["command"] == "apoch"


class TestDiscardInstall:
    """OpenCodeAdapter.discard_install() behavior."""

    def test_discard_removes_backup(self, tmp_path) -> None:
        """discard_install() removes the backup file."""
        from apoch.adapters.opencode.server import InstallPlan, OpenCodeAdapter

        backup_path = tmp_path / "backup.json"
        backup_path.write_text("{}")

        plan = InstallPlan(backup_path=backup_path, current={}, proposed={})
        adapter = OpenCodeAdapter(config={})
        adapter.discard_install(plan)

        assert not backup_path.exists()

    def test_discard_idempotent(self, tmp_path) -> None:
        """discard_install() is idempotent — second call is a no-op."""
        from apoch.adapters.opencode.server import InstallPlan, OpenCodeAdapter

        backup_path = tmp_path / "backup.json"
        backup_path.write_text("{}")

        plan = InstallPlan(backup_path=backup_path, current={}, proposed={})
        adapter = OpenCodeAdapter(config={})
        adapter.discard_install(plan)
        # Second call should not raise
        adapter.discard_install(plan)
        assert not backup_path.exists()


class TestUninstall:
    """OpenCodeAdapter.uninstall() behavior."""

    def test_uninstall_restores_backup(self, tmp_path, monkeypatch) -> None:
        """uninstall() restores opencode.json from the latest backup."""
        from apoch.adapters.opencode.server import OpenCodeAdapter

        # Set up a real backup directory
        opencode_path = tmp_path / ".opencode" / "opencode.json"
        opencode_path.parent.mkdir(parents=True)
        opencode_path.write_text(json.dumps({"mcpServers": {"apoch": {"command": "apoch"}}}))

        backup_dir = opencode_path.parent / ".apoch-backups"
        backup_dir.mkdir(parents=True)
        backup_path = backup_dir / "opencode-20250101_000000.json"
        backup_path.write_text(json.dumps({"original": "config"}))

        monkeypatch.chdir(tmp_path)

        adapter = OpenCodeAdapter(config={})
        adapter.uninstall()

        restored = json.loads(opencode_path.read_text())
        assert restored == {"original": "config"}

    def test_uninstall_no_backups_is_noop(self, tmp_path, monkeypatch) -> None:
        """uninstall() is a no-op when no backups exist."""
        from apoch.adapters.opencode.server import OpenCodeAdapter

        opencode_path = tmp_path / ".opencode" / "opencode.json"
        opencode_path.parent.mkdir(parents=True)
        opencode_path.write_text(json.dumps({"apoch": "installed"}))

        monkeypatch.chdir(tmp_path)

        adapter = OpenCodeAdapter(config={})
        # Should not raise when no backup dir exists
        adapter.uninstall()

        # Config should remain untouched
        assert json.loads(opencode_path.read_text()) == {"apoch": "installed"}
