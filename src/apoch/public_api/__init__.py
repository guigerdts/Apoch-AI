"""Public API layer for Apoch-AI.

Provides typed, versioned, and tested infrastructure for all MCP tools
without modifying visible system behavior. See ADR-001 through ADR-005.
"""

from apoch.public_api.version import API_VERSION

__all__ = [
    "API_VERSION",
    "models",
    "registry",
    "version",
    "errors",
    "metrics",
    "coordinator",
]
