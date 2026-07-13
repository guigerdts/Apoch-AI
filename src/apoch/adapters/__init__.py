"""Agent adapters — connectors to AI coding agents.

This package defines the ``AgentAdapter`` ABC that every concrete adapter
(OpenCode, Gentle-AI, etc.) must implement.  The Core depends ONLY on
this ABC — never on a concrete adapter.
"""

from apoch.adapters.base import AgentAdapter, HealthStatus, ToolDef

__all__ = [
    "AgentAdapter",
    "HealthStatus",
    "ToolDef",
]
