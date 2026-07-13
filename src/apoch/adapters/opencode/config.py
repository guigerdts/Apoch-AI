"""opencode.json configuration manager.

Spec: cli-interface §Install Module, §Execution Flow
Architecture: This module is the ONLY place that reads/writes opencode.json.
No other module may import ``json`` or manipulate opencode.json directly.

Design: ``OpenCodeConfig`` model with ``read``, ``write``, ``validate``,
``merge``, ``backup``, and ``rollback``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from apoch.core.exceptions import OpenCodeConfigError

logger = logging.getLogger(__name__)

# Default opencode.json location (relative to project root or $HOME)
_DEFAULT_OPENCODE_PATH = Path(".opencode/opencode.json")

# JSONC comment detection — files containing these patterns are treated as JSONC
_JSONC_PATTERN = re.compile(r"^\s*(//|/\*)")


def _looks_like_jsonc(raw: str) -> bool:
    """Return True if *raw* appears to contain JSONC-style comments."""
    for line in raw.splitlines():
        if _JSONC_PATTERN.match(line):
            return True
    return "/*" in raw and "*/" in raw


class OpenCodeConfig:
    """Manage the opencode.json configuration file for OpenCode integration.

    Usage::

        cfg = OpenCodeConfig()
        current = cfg.read()
        desired = cfg.merge(current)
        backup_path = cfg.backup()
        cfg.write(desired)
        # ... if something goes wrong:
        cfg.rollback(backup_path)
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path: Path = Path(path).resolve() if path else _path_from_cwd()
        self._backup_dir: Path = self._path.parent / ".apoch-backups"

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        """Parse and return the current opencode.json content.

        Returns an empty dict if the file does not exist. Detects JSONC
        (JSON with comments) and preserves the raw format for writes.

        Raises:
            OpenCodeConfigError: If the file contains unparseable JSON.
        """
        if not self._path.exists():
            return {}

        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise OpenCodeConfigError(f"Cannot read {self._path}: {exc}") from exc

        if not raw.strip():
            return {}

        # Attempt to parse — strip comments for JSONC
        if _looks_like_jsonc(raw):
            cleaned = _strip_jsonc_comments(raw)
        else:
            cleaned = raw

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise OpenCodeConfigError(f"Invalid JSON in {self._path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, data: dict[str, Any]) -> None:
        """Serialize *data* to opencode.json (atomic write).

        Writes to a temporary file first, then renames to the target
        path — prevents corruption if the process is interrupted.

        Preserves any existing MCP servers and non-Apoch keys in the
        file.  If the original file was JSONC, the output is standard
        JSON (the user can re-add comments manually).

        Raises:
            OpenCodeConfigError: If the file cannot be written.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        try:
            fd, tmp_path_str = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=".opencode-",
                suffix=".tmp",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path_str, str(self._path))
        except OSError as exc:
            raise OpenCodeConfigError(f"Cannot write {self._path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate *data* as a well-formed opencode.json for Apoch-AI.

        Returns a list of error messages (empty = valid).
        """
        errors: list[str] = []

        if not isinstance(data, dict):
            errors.append("Root value must be a JSON object")
            return errors

        servers = data.get("mcpServers")
        if servers is None:
            errors.append("Missing required key: 'mcpServers'")
            return errors

        if not isinstance(servers, dict):
            errors.append("'mcpServers' must be a JSON object")
            return errors

        apoch_entry = servers.get("apoch")
        if apoch_entry is None:
            errors.append("Missing required entry 'apoch' under 'mcpServers'")
            return errors

        if not isinstance(apoch_entry, dict):
            errors.append("'apoch' entry must be a JSON object")
            return errors

        if "command" not in apoch_entry:
            errors.append("'apoch' entry is missing required field 'command'")

        return errors

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge(self, current: dict[str, Any]) -> dict[str, Any]:
        """Add or update the Apoch-AI entry in *current*, preserving all other keys.

        The returned dict is a deep-enough copy — existing MCP servers
        are preserved, and only the ``apoch`` entry under
        ``mcpServers`` is added/updated.
        """
        result: dict[str, Any] = dict(current)

        servers: dict[str, Any] = dict(result.get("mcpServers", {}))
        servers["apoch"] = {
            "command": "apoch",
            "args": ["mcp"],
            "description": "Apoch-AI MCP gateway",
        }
        result["mcpServers"] = servers

        return result

    # ------------------------------------------------------------------
    # Backup and rollback
    # ------------------------------------------------------------------

    def backup(self) -> Path:
        """Create a timestamped backup of the current opencode.json.

        Returns the path to the backup file.

        Raises:
            OpenCodeConfigError: If the backup cannot be created.
        """
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OpenCodeConfigError(
                f"Cannot create backup directory {self._backup_dir}: {exc}"
            ) from exc

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"opencode-{timestamp}.json"

        try:
            if self._path.exists():
                shutil.copy2(self._path, backup_path)
            else:
                backup_path.write_text("{}\n", encoding="utf-8")
        except OSError as exc:
            raise OpenCodeConfigError(f"Cannot create backup at {backup_path}: {exc}") from exc

        logger.info("Backup created: %s", backup_path)
        return backup_path

    def rollback(self, backup_path: str | Path) -> None:
        """Restore opencode.json from *backup_path*.

        Raises:
            OpenCodeConfigError: If the backup cannot be found or restored.
        """
        src = Path(backup_path)
        if not src.exists():
            raise OpenCodeConfigError(f"Backup not found: {src}")
        try:
            shutil.copy2(src, self._path)
        except OSError as exc:
            raise OpenCodeConfigError(f"Cannot restore backup from {src}: {exc}") from exc
        logger.info("Rolled back to: %s", src)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _path_from_cwd() -> Path:
    """Resolve the default opencode.json path from the current directory.

    Walks up from CWD looking for ``.opencode/opencode.json``.  Falls
    back to ``~/.opencode/opencode.json``.
    """
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / ".opencode" / "opencode.json"
        if candidate.exists():
            return candidate
    return Path.home() / ".opencode" / "opencode.json"


def _strip_jsonc_comments(raw: str) -> str:
    """Remove JSONC comments for parsing."""
    lines: list[str] = []
    in_block = False
    for line in raw.splitlines():
        stripped = line.strip()
        if in_block:
            end = stripped.find("*/")
            if end != -1:
                in_block = False
                remaining = stripped[end + 2 :]
                if remaining:
                    lines.append(remaining)
            continue
        if stripped.startswith("//"):
            continue
        if "/*" in stripped:
            start = stripped.find("/*")
            before = stripped[:start]
            if before:
                lines.append(before)
            in_block = "*/" not in stripped[start + 2 :]
            continue
        lines.append(line)
    return "\n".join(lines)
