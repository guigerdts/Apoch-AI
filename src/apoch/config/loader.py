"""YAML + environment-variable configuration loader.

The ``ConfigLoader`` reads configuration from three sources in ascending
precedence:

    1. ``apoch.config.defaults.fresh_defaults()``
2. YAML config file (``$APOCH_CONFIG`` or ``~/.config/apoch/config.yaml``)
3. ``APOCH_*`` environment variables (e.g. ``APOCH_LOG_LEVEL``)

Spec: module-system §Config Override
Design: Config Format (YAML primary + env var overrides)
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import yaml

from apoch.config.defaults import ENV_KEY_MAP, KNOWN_KEYS, fresh_defaults
from apoch.core.exceptions import ConfigError


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Deep-merge *overlay* into *base*, mutating and returning *base*."""
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class ConfigLoader:
    """Loads and merges Apoch-AI configuration.

    Usage::

        loader = ConfigLoader()
        config = loader.load()          # all sources merged
        print(config["log_level"])      # "info" (default)

    Pass an explicit *config_path* to override automatic file resolution::

        loader = ConfigLoader(config_path=Path("/custom/path.yaml"))
        config = loader.load()
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._explicit_path: Path | None = Path(config_path).resolve() if config_path else None

    def load(self) -> dict:
        """Load, merge, and return the effective configuration dict.

        Precedence (last wins):
            1. Hardcoded defaults
            2. YAML file (if it exists)
            3. ``APOCH_*`` environment variables
        """
        config: dict = fresh_defaults()  # fresh copy — no shared mutable state

        path = self._resolve_config_path()
        if path is not None and path.exists():
            try:
                raw = path.read_text(encoding="utf-8")
                yaml_config: dict = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                raise ConfigError(f"Malformed YAML config at {path}: {exc}") from exc

            # Warn about unknown keys
            for key in yaml_config:
                if key not in KNOWN_KEYS:
                    warnings.warn(f"Unknown config key '{key}' in {path}", stacklevel=2)

            config = _deep_merge(config, yaml_config)

        # Environment variable overlays (highest precedence)
        for env_var, config_key in ENV_KEY_MAP.items():
            value = os.environ.get(env_var)
            if value is not None:
                config[config_key] = value

        return config

    def _resolve_config_path(self) -> Path | None:
        """Return the config file path, or ``None`` if no path can be determined.

        Resolution order:
            1. Explicit path passed to the constructor
            2. ``$APOCH_CONFIG`` environment variable
            3. ``~/.config/apoch/config.yaml`` (platform default)
        """
        if self._explicit_path is not None:
            return self._explicit_path

        env_config = os.environ.get("APOCH_CONFIG")
        if env_config:
            return Path(env_config)

        return Path.home() / ".config" / "apoch" / "config.yaml"
