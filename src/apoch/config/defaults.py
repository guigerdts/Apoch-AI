"""Default configuration values for Apoch-AI.

Spec: module-system §Config Override
Design: Config Format (YAML primary + env var overrides)
"""

# ---------------------------------------------------------------------------
# Default configuration dictionary
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "log_level": "info",
    "home": None,  # resolved at runtime by ConfigLoader
    "modules": {},
}


def fresh_defaults() -> dict:
    """Return a fresh copy of the default configuration dict.

    Avoids sharing mutable ``dict`` objects across calls so that callers
    cannot accidentally mutate the module-level constant.
    """
    return {
        "log_level": "info",
        "home": None,
        "modules": {},
    }


# Known config keys — used to detect unknown keys in user YAML
KNOWN_KEYS: frozenset = frozenset(DEFAULT_CONFIG.keys())

# Environment variable → config key mapping
# APOCH_* env vars are overlaid AFTER YAML merge, so they take highest
# precedence.
ENV_KEY_MAP: dict[str, str] = {
    "APOCH_LOG_LEVEL": "log_level",
    "APOCH_HOME": "home",
}
