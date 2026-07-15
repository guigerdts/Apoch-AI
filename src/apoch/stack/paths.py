"""Filesystem path resolution for the Core Stack.

All stack-related paths are resolved through this single module using
platform-native directory conventions:

* **Linux / Termux**: XDG Base Directory (``~/.config``, ``~/.local/share``).
* **macOS**: ``~/Library/Preferences``, ``~/Library/Application Support``.
* **Windows**: ``%APPDATA%`` (Roaming), ``%LOCALAPPDATA%`` (Local).

Customisation (any platform):

* ``$XDG_CONFIG_HOME`` / ``$XDG_DATA_HOME`` override the base directory
  (highest precedence, backward compatible).

Design: Core Stack Installation & Lifecycle — StackPaths
"""

from __future__ import annotations

import os
import platform as _platform
from pathlib import Path


def _platform_defaults(system: str | None = None) -> tuple[Path, Path]:
    """Return ``(config_base, data_base)`` for the given operating system.

    Args:
        system: OS identifier (``platform.system()`` output).  ``None``
                auto-detects the current platform.

    Returns:
        A tuple of ``(config_base_directory, data_base_directory)``.
    """
    sys_name = system or _platform.system()
    home = Path.home()

    if sys_name == "Windows":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        return (
            Path(appdata) if appdata else home / "AppData" / "Roaming",
            Path(localappdata) if localappdata else home / "AppData" / "Local",
        )

    if sys_name == "Darwin":
        return (
            home / "Library" / "Preferences",
            home / "Library" / "Application Support",
        )

    # Linux, Termux, BSD, others → XDG defaults
    return (
        home / ".config",
        home / ".local" / "share",
    )


def _env_or_default(name: str, default: Path) -> Path:
    """Return the path from an environment variable, or the default."""
    val = os.environ.get(name)
    if val:
        return Path(val)
    return default


class StackPaths:
    """Centralised path resolution for stack files and directories.

    Platform-native base directories are used unless overridden via
    ``$XDG_CONFIG_HOME`` or ``$XDG_DATA_HOME`` (backward compatible).

    Attributes:
        config_home: Root for configuration files
                     (platform-native or overridden).
        data_home:   Root for data files
                     (platform-native or overridden).
    """

    def __init__(self, stack_name: str = "apoch") -> None:
        config_fallback, data_fallback = _platform_defaults()
        config_base = _env_or_default("XDG_CONFIG_HOME", config_fallback)
        data_base = _env_or_default("XDG_DATA_HOME", data_fallback)
        self.config_home: Path = config_base / stack_name / "stack"
        self.data_home: Path = data_base / stack_name / "stack"

    # ── Shorthand constructors ───────────────────────────────────────

    @classmethod
    def for_apoch(cls) -> StackPaths:
        """Create a ``StackPaths`` for the ``apoch`` namespace."""
        return cls("apoch")

    # ── Common paths ─────────────────────────────────────────────────

    def manifest_path(self) -> Path:
        """Return the path to the global stack manifest."""
        return self.data_home / "manifest.yaml"

    def lock_path(self) -> Path:
        """Return the path to the stack lock file."""
        return self.data_home / "stack.lock"

    def component_config_dir(self, component_name: str) -> Path:
        """Return the directory for a specific component's config files."""
        return self.config_home / component_name

    def component_data_dir(self, component_name: str) -> Path:
        """Return the directory for a specific component's data files."""
        return self.data_home / component_name

    def stack_root(self) -> Path:
        """Return the root directory used for stack management."""
        return self.data_home
