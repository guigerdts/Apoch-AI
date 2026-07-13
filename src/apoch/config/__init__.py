"""Apoch-AI configuration loading and management.

This package is a **leaf** — it MUST NOT import from any other Apoch-AI
internal package (``apoch.core.*``, ``apoch.cli.*``, ``apoch.modules.*``,
etc.). It depends only on the stdlib and PyYAML.
"""

from apoch.config.loader import ConfigError, ConfigLoader

__all__ = [
    "ConfigError",
    "ConfigLoader",
]
