"""OpenCode adapter — FastMCP gateway over stdio transport.

Architecture rule: This package is the ONLY place that imports FastMCP.
No other package in Apoch-AI may depend on ``mcp`` or FastMCP classes.

Design constraint: If the MCP protocol or library changes, only this
package needs to be updated — the ``AgentAdapter`` ABC remains stable.
"""

from apoch.adapters.opencode.config import OpenCodeConfig
from apoch.adapters.opencode.server import OpenCodeAdapter

__all__ = [
    "OpenCodeAdapter",
    "OpenCodeConfig",
]
