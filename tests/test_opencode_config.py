"""Tests for opencode.json configuration manager (RED phase).

Spec: cli-interface §Install Module, §Execution Flow
Architecture: opencode.json management lives ONLY in adapters/opencode/config.py.
Design: OpenCodeConfig model with read/write/validate/merge.

RED-GREEN phases:
  RED:   Tests MUST fail — config.py does not exist yet.
  GREEN: After creating config.py, all tests MUST pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestOpenCodeConfigModel:
    """OpenCodeConfig model — read/write/validate/merge."""

    def test_config_model_importable(self) -> None:
        """RED: OpenCodeConfig is importable from adapters.opencode.config."""
        from apoch.adapters.opencode.config import OpenCodeConfig  # noqa: F401

    def test_config_model_has_read(self) -> None:
        """OpenCodeConfig has a read() method."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        assert hasattr(cfg, "read")

    def test_config_model_has_write(self) -> None:
        """OpenCodeConfig has a write() method."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        assert hasattr(cfg, "write")

    def test_config_model_has_validate(self) -> None:
        """OpenCodeConfig has a validate() method."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        assert hasattr(cfg, "validate")

    def test_config_model_has_merge(self) -> None:
        """OpenCodeConfig has a merge() method."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        assert hasattr(cfg, "merge")


class TestOpenCodeConfigRead:
    """Read existing opencode.json."""

    def test_read_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        """read() returns empty config when file does not exist."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig(path=tmp_path / "opencode.json")
        result = cfg.read()
        assert result == {}

    def test_read_returns_parsed_json(self, tmp_path: Path) -> None:
        """read() returns parsed content of a valid opencode.json."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        path.write_text(json.dumps({"mcpServers": {}}))
        cfg = OpenCodeConfig(path=path)
        result = cfg.read()
        assert "mcpServers" in result

    def test_read_invalid_json_raises_error(self, tmp_path: Path) -> None:
        """read() raises OpenCodeConfigError on invalid JSON."""
        from apoch.adapters.opencode.config import OpenCodeConfig
        from apoch.core.exceptions import OpenCodeConfigError

        path = tmp_path / "opencode.json"
        path.write_text("not valid json{")
        cfg = OpenCodeConfig(path=path)
        with pytest.raises(OpenCodeConfigError):
            cfg.read()


class TestOpenCodeConfigWrite:
    """Write opencode.json."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """write() creates the opencode.json file."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        cfg = OpenCodeConfig(path=path)
        cfg.write({"mcpServers": {"apoch": {"command": "apoch", "args": ["mcp"]}}})
        assert path.exists()

    def test_write_content_is_valid_json(self, tmp_path: Path) -> None:
        """write() produces valid JSON that can be re-read."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        expected = {"mcpServers": {"apoch": {"command": "apoch", "args": ["mcp"]}}}
        cfg = OpenCodeConfig(path=path)
        cfg.write(expected)
        parsed = json.loads(path.read_text())
        assert parsed == expected

    def test_write_preserves_existing_keys(self, tmp_path: Path) -> None:
        """write() preserves keys that are not part of Apoch's config."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        existing = {
            "otherTool": {"setting": 42},
            "mcpServers": {"other_server": {"command": "other"}},
        }
        path.write_text(json.dumps(existing))

        cfg = OpenCodeConfig(path=path)
        # Need to merge, not just write
        current = cfg.read()
        current.setdefault("mcpServers", {})["apoch"] = {
            "command": "apoch",
            "args": ["mcp"],
        }
        cfg.write(current)
        parsed = json.loads(path.read_text())
        assert parsed["otherTool"]["setting"] == 42
        assert "other_server" in parsed["mcpServers"]
        assert "apoch" in parsed["mcpServers"]


class TestOpenCodeConfigValidate:
    """Validate opencode.json structure."""

    def test_validate_valid_config(self) -> None:
        """validate() returns empty list for valid config."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        errors = cfg.validate(
            {
                "mcpServers": {
                    "apoch": {"command": "apoch", "args": ["mcp"]},
                },
            }
        )
        assert errors == []

    def test_validate_missing_mcp_servers(self) -> None:
        """validate() flags missing mcpServers key."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        errors = cfg.validate({})
        assert len(errors) > 0

    def test_validate_missing_apoch_entry(self) -> None:
        """validate() flags missing apoch entry in mcpServers."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        cfg = OpenCodeConfig()
        errors = cfg.validate({"mcpServers": {}})
        assert len(errors) > 0


class TestOpenCodeConfigMerge:
    """Merge desired Apoch config into opencode.json."""

    def test_merge_adds_apoch_entry(self, tmp_path: Path) -> None:
        """merge() adds apoch MCP server entry."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        cfg = OpenCodeConfig(path=path)
        result = cfg.merge({})
        assert "mcpServers" in result
        assert "apoch" in result["mcpServers"]

    def test_merge_preserves_existing_servers(self, tmp_path: Path) -> None:
        """merge() does not remove existing MCP servers."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        path.write_text(
            json.dumps(
                {
                    "mcpServers": {"existing": {"command": "tool"}},
                }
            )
        )
        cfg = OpenCodeConfig(path=path)
        current = cfg.read()
        result = cfg.merge(current)
        assert "existing" in result["mcpServers"]
        assert "apoch" in result["mcpServers"]

    def test_merge_idempotent(self, tmp_path: Path) -> None:
        """merge() applied twice produces the same result."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        cfg = OpenCodeConfig(path=path)

        first = cfg.merge({})
        cfg.write(first)
        second = cfg.merge(first)
        assert first == second


class TestBackupAndRollback:
    """Backup and rollback operations."""

    def test_backup_creates_timestamped_copy(self, tmp_path: Path) -> None:
        """backup() creates a timestamped copy of opencode.json."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        path.write_text(json.dumps({"version": "original"}))
        cfg = OpenCodeConfig(path=path)
        backup_path = cfg.backup()
        assert backup_path.exists()
        assert "opencode" in backup_path.name

    def test_rollback_restores_backup(self, tmp_path: Path) -> None:
        """rollback() restores the config from backup."""
        from apoch.adapters.opencode.config import OpenCodeConfig

        path = tmp_path / "opencode.json"
        path.write_text(json.dumps({"version": "original"}))
        cfg = OpenCodeConfig(path=path)
        backup_path = cfg.backup()

        # Modify the config
        path.write_text(json.dumps({"version": "modified"}))

        # Rollback
        cfg.rollback(backup_path)
        restored = json.loads(path.read_text())
        assert restored["version"] == "original"
