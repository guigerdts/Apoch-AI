"""Tests for StackPaths — filesystem path resolution.

Design: Core Stack Installation & Lifecycle — StackPaths
"""

from __future__ import annotations

from pathlib import Path

from apoch.stack.paths import StackPaths, _platform_defaults


class TestPlatformDefaults:
    """Verify platform-specific default directories."""

    def test_linux_defaults(self):
        """Linux uses XDG directories."""
        cfg, data = _platform_defaults(system="Linux")
        assert cfg == Path.home() / ".config"
        assert data == Path.home() / ".local" / "share"

    def test_macos_defaults(self):
        """macOS uses Library directories."""
        cfg, data = _platform_defaults(system="Darwin")
        assert cfg == Path.home() / "Library" / "Preferences"
        assert data == Path.home() / "Library" / "Application Support"

    def test_windows_defaults(self):
        """Windows uses APPDATA directories."""
        cfg, data = _platform_defaults(system="Windows")
        assert "AppData" in str(cfg)
        assert "AppData" in str(data)

    def test_windows_defaults_falls_back_when_no_env(self, monkeypatch):
        """Windows fallback when APPDATA/LOCALAPPDATA are unset."""
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        cfg, data = _platform_defaults(system="Windows")
        assert cfg == Path.home() / "AppData" / "Roaming"
        assert data == Path.home() / "AppData" / "Local"

    def test_termux_defaults(self):
        """Termux (Linux) uses XDG defaults."""
        cfg, data = _platform_defaults(system="Linux")
        assert ".config" in str(cfg)
        assert ".local" in str(data)


class TestStackPaths:
    """Verify path resolution behaviour."""

    def test_default_config_home(self):
        """Default config_home uses platform-native base."""
        paths = StackPaths.for_apoch()
        cfg_base, _ = _platform_defaults()
        assert paths.config_home == cfg_base / "apoch" / "stack"

    def test_default_data_home(self):
        """Default data_home uses platform-native base."""
        paths = StackPaths.for_apoch()
        _, data_base = _platform_defaults()
        assert paths.data_home == data_base / "apoch" / "stack"

    def test_manifest_path(self):
        """manifest_path() returns the correct path."""
        paths = StackPaths.for_apoch()
        assert paths.manifest_path() == paths.data_home / "manifest.yaml"

    def test_lock_path(self):
        """lock_path() returns the correct path."""
        paths = StackPaths.for_apoch()
        assert paths.lock_path() == paths.data_home / "stack.lock"

    def test_component_config_dir(self):
        """component_config_dir() returns the config home plus component name."""
        paths = StackPaths.for_apoch()
        assert paths.component_config_dir("engram") == paths.config_home / "engram"

    def test_component_data_dir(self):
        """component_data_dir() returns the data home plus component name."""
        paths = StackPaths.for_apoch()
        assert paths.component_data_dir("engram") == paths.data_home / "engram"

    def test_stack_root(self):
        """stack_root() returns data_home."""
        paths = StackPaths.for_apoch()
        assert paths.stack_root() == paths.data_home

    def test_custom_stack_name(self):
        """A custom stack name produces different paths."""
        paths = StackPaths("my-stack")
        assert "my-stack" in str(paths.config_home)
        assert "my-stack" in str(paths.data_home)

    def test_env_override_config(self, monkeypatch):
        """XDG_CONFIG_HOME overrides the config base directory."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        paths = StackPaths.for_apoch()
        assert str(paths.config_home) == "/custom/config/apoch/stack"

    def test_env_override_data(self, monkeypatch):
        """XDG_DATA_HOME overrides the data base directory."""
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        paths = StackPaths.for_apoch()
        assert str(paths.data_home) == "/custom/data/apoch/stack"

    def test_xdg_overrides_platform_on_macos(self, monkeypatch):
        """XDG vars take precedence over macOS defaults."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/config")
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg/data")
        paths = StackPaths.for_apoch()
        # The XDG override should win regardless of platform
        assert str(paths.config_home) == "/xdg/config/apoch/stack"
        assert str(paths.data_home) == "/xdg/data/apoch/stack"
