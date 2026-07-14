"""Agent adapter ABC — contract for every AI agent connector.

Spec: agent-adapter §Adapter ABC Contract
Architecture: The Core MUST NOT depend on any concrete adapter.  This ABC
is the ONLY bridge between Core and any agent-specific implementation.

Design constraints:
- Zero dependency on FastMCP, OpenCode, or any MCP library.
- Only stdlib: ``abc``, ``dataclasses``, ``typing``.
- ``HealthStatus`` and ``ToolDef`` are defined here as pure data types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class HealthStatus:
    """Result of an adapter health check.

    Attributes:
        healthy:        ``True`` if the gateway process is responsive.
        uptime_seconds: Seconds since the gateway started, or ``None``.
        error:          Error description if not healthy, or ``None``.
    """

    healthy: bool
    uptime_seconds: float | None = None
    error: str | None = None


@dataclass
class ToolDef:
    """Descriptor for a single MCP tool exposed by a module.

    Attributes:
        name:         Tool name (unique within the module namespace).
        description:  Human-readable description of the tool's purpose.
        input_schema: JSON Schema dict describing the expected parameters.
        handler_name: Name of the public method on the module instance that
                      implements this tool.  Must be resolvable via
                      ``getattr(module, handler_name)`` at registration time.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler_name: str


class AgentAdapter(ABC):
    """Abstract base for all AI agent adapters.

    Every concrete adapter (OpenCode, Gentle-AI, etc.) MUST implement all
    four abstract methods.  The adapter receives its configuration as a
    ``config`` dict at construction time.
    """

    def __init__(self, config: dict) -> None:
        self._config: dict = config

    @abstractmethod
    async def start(self) -> None:
        """Start the adapter's gateway process.

        Must be idempotent — calling ``start()`` on an already-started
        adapter should be a no-op.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter's gateway process gracefully.

        Must be idempotent — calling ``stop()`` on an already-stopped
        adapter should be a no-op.
        """

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Return the current health status of the gateway process."""

    @abstractmethod
    async def register_module_tools(
        self, module_name: str, module: Any, tools: list[ToolDef]
    ) -> None:
        """Register *tools* belonging to *module_name* with the gateway.

        *module* is the module instance used to resolve ``handler_name``
        on each ``ToolDef`` via ``getattr(module, tool.handler_name)``.

        If a tool name conflicts with an already-registered tool, the
        adapter MUST prefix the tool name (e.g. ``module_name_tool``)
        and log a warning.
        """
