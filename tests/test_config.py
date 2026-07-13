"""Tests for config loader (RED phase — config package doesn't exist yet).

Spec: module-system §Config Override
"""

import warnings
from pathlib import Path

import pytest


class TestConfigError:
    """ConfigError is defined in the config package (not core.exceptions)."""

    def test_config_error_exists(self):
        """ConfigError extends ApochError."""
        from apoch.config import ConfigError
        from apoch.core.exceptions import ApochError

        assert issubclass(ConfigError, ApochError)

    def test_config_error_is_raiseable(self):
        """ConfigError can be raised with a message."""
        from apoch.config import ConfigError

        with pytest.raises(ConfigError) as exc_info:
            raise ConfigError("Malformed YAML")
        assert "Malformed YAML" in str(exc_info.value)


class TestDefaultConfig:
    """ConfigLoader returns defaults when no config file or env vars are set."""

    def test_default_config_contains_log_level(self):
        """Default config has log_level key."""
        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert isinstance(config, dict)
        assert "log_level" in config

    def test_default_log_level_is_info(self):
        """Default log_level is 'info'."""
        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert config["log_level"] == "info"

    def test_default_config_contains_home(self):
        """Default config has home key."""
        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert "home" in config

    def test_default_config_contains_modules(self):
        """Default config has modules key."""
        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert "modules" in config
        assert config["modules"] == {}


class TestYamlLoading:
    """ConfigLoader reads YAML from file path."""

    def test_yaml_file_content_loaded(self, tmp_path: Path):
        """YAML values appear in loaded config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: debug\n")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config["log_level"] == "debug"

    def test_yaml_merges_over_defaults(self, tmp_path: Path):
        """YAML values override defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: error\n")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config["log_level"] == "error"


class TestEnvVarOverlay:
    """APOCH_* environment variables override YAML and defaults."""

    def test_apoch_log_level_env_var(self, tmp_path: Path, monkeypatch):
        """APOCH_LOG_LEVEL overrides config file value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: info\n")
        monkeypatch.setenv("APOCH_LOG_LEVEL", "debug")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        config = loader.load()
        assert config["log_level"] == "debug"

    def test_apoch_home_env_var_overrides_default(self, monkeypatch):
        """APOCH_HOME env var sets home in config."""
        monkeypatch.setenv("APOCH_HOME", "/tmp/apoch_test")

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert config["home"] == "/tmp/apoch_test"


class TestDeepMerge:
    """Merge precedence: defaults < YAML < env vars."""

    def test_yaml_overrides_defaults(self, tmp_path: Path):
        """YAML value beats default."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: warning\n")

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader(config_path=config_file).load()
        assert config["log_level"] == "warning"

    def test_env_overrides_yaml(self, tmp_path: Path, monkeypatch):
        """Env var beats YAML value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: warning\n")
        monkeypatch.setenv("APOCH_LOG_LEVEL", "critical")

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader(config_path=config_file).load()
        assert config["log_level"] == "critical"

    def test_env_overrides_default_when_no_yaml(self, monkeypatch):
        """Env var beats default when no config file exists."""
        monkeypatch.setenv("APOCH_LOG_LEVEL", "error")

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader().load()
        assert config["log_level"] == "error"


class TestMissingFile:
    """Missing config file returns defaults without error."""

    def test_missing_config_file_returns_defaults(self, tmp_path: Path):
        """Non-existent file path returns default config."""
        missing = tmp_path / "nonexistent.yaml"
        assert not missing.exists()

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader(config_path=missing).load()
        assert config["log_level"] == "info"
        assert config["modules"] == {}


class TestMalformedYaml:
    """Malformed YAML raises ConfigError."""

    def test_malformed_yaml_raises_config_error(self, tmp_path: Path):
        """Broken YAML content raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(": invalid yaml :\n")

        from apoch.config import ConfigError
        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        with pytest.raises(ConfigError):
            loader.load()

    def test_malformed_yaml_message_includes_path(self, tmp_path: Path):
        """ConfigError message includes the problematic file path."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: [\n")

        from apoch.config import ConfigError
        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        with pytest.raises(ConfigError) as exc_info:
            loader.load()
        assert str(config_file) in str(exc_info.value)


class TestUnknownKeys:
    """Unknown keys in config warn but don't crash."""

    def test_unknown_key_emits_warning(self, tmp_path: Path):
        """Strange keys emit a UserWarning."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("unknown_key: true\nlog_level: info\n")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        with pytest.warns(UserWarning) as record:
            config = loader.load()

        assert config["log_level"] == "info"
        warning_messages = [str(w.message) for w in record]
        assert any("unknown_key" in msg for msg in warning_messages)

    def test_empty_yaml_keeps_defaults(self, tmp_path: Path):
        """Empty YAML (whitespace only) keeps defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("\n\n")

        from apoch.config.loader import ConfigLoader

        config = ConfigLoader(config_path=config_file).load()
        assert config["log_level"] == "info"

    def test_only_unknown_keys_keeps_defaults(self, tmp_path: Path):
        """YAML with only unknown keys warns but keeps all defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("strange_setting: 42\nverbose: true\n")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        with pytest.warns(UserWarning) as record:
            config = loader.load()

        assert config["log_level"] == "info"
        assert config["modules"] == {}
        messages = [str(w.message) for w in record]
        assert any("strange_setting" in msg for msg in messages)
        assert any("verbose" in msg for msg in messages)

    def test_known_keys_do_not_warn(self, tmp_path: Path):
        """Known keys do not emit warnings."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("log_level: debug\nmodules: {}\n")

        from apoch.config.loader import ConfigLoader

        loader = ConfigLoader(config_path=config_file)
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            config = loader.load()

        assert config["log_level"] == "debug"
        warning_list = [w for w in record if issubclass(w.category, UserWarning)]
        assert len(warning_list) == 0
