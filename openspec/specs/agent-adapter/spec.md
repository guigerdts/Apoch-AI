# Agent Adapter Specification

## Objective

Enable Apoch-AI modules to communicate with AI agents through a standardized adapter interface, keeping the Core completely agent-agnostic. In v1, the OpenCode adapter serves as the single MCP gateway over stdio transport.

## Responsibilities

- Define the `AgentAdapter` ABC that any agent connector must implement
- Provide the OpenCode-specific adapter implementing MCP protocol over stdio
- Start, stop, and health-check the single MCP gateway process
- Expose module capabilities as MCP tools, resources, and prompts
- Manage opencode.json configuration for the MCP server entry
- Support `apoch mcp {start, stop, restart}` from CLI

## Scope

### In Scope
- `AgentAdapter` ABC with abstract methods for all agent interaction
- `OpenCodeAdapter` implementation using FastMCP (or equivalent) over stdio
- Single gateway server that aggregates all module tools under one process
- Module tool registration (each module declares its tools; gateway aggregates them)
- Gateway health check and restart logic
- Entry point for `apoch mcp` subcommand lifecycle
- stdio transport only (JSON-RPC 2.0 over stdin/stdout)

### Out of Scope
- Per-module MCP servers (v1.1+, each module gets its own process)
- Remote agent adapters (HTTP, WebSocket — future)
- SSE or WebSocket transport (future)
- Agent other than OpenCode in v1 (Gentle-AI deferred)

## Architecture

```
CLI → apoch mcp start → AgentAdapterManager → OpenCodeAdapter
                                                  │
                                            FastMCP Server (stdio)
                                                  │
                              ┌───────────────────┼──────────────────┐
                          Module A tools      Module B tools    Module C tools
```

The `AgentAdapterManager` instantiates the configured adapter, starts it, and monitors its health. The adapter itself is a FastMCP server running as a long-lived stdio process. Modules register their tools with the adapter during initialization.

## Public Interfaces

### `AgentAdapter` ABC

```python
class AgentAdapter(ABC):
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def health(self) -> HealthStatus: ...
    @abstractmethod
    async def register_module_tools(self, module_name: str, tools: list[ToolDef]) -> None: ...
```

### `AgentAdapterManager`

```python
class AgentAdapterManager:
    def __init__(self, adapter: AgentAdapter) -> None: ...
    async def start_gateway(self) -> None: ...
    async def stop_gateway(self) -> None: ...
    async def restart_gateway(self) -> None: ...
    async def health(self) -> GatewayHealth: ...
```

## Execution Flow: MCP Gateway Start

1. CLI receives `apoch mcp start`
2. `AgentAdapterManager` loads the configured adapter (default: OpenCodeAdapter)
3. Adapter starts: creates FastMCP server, registers all loaded module tools
4. Server listens on stdio (reads JSON-RPC requests from stdin, writes to stdout)
5. Manager runs a health check (sends `ping`, receives `pong`)
6. Manager reports status to CLI

## Dependencies

- **Internal**: ModuleRegistry (for module tool registration), CLI Interface (for `apoch mcp`)
- **External**: FastMCP or equivalent MCP server library, Python stdlib `asyncio`, `json`

## Requirements

### Requirement: Adapter ABC Contract

The Core MUST define an `AgentAdapter` ABC that any agent-specific adapter implements. The Core MUST NOT depend on any concrete adapter.

#### Scenario: OpenCodeAdapter conforms to ABC

- GIVEN an `OpenCodeAdapter` implementation
- WHEN checked for ABC conformance
- THEN it MUST pass `issubclass(OpenCodeAdapter, AgentAdapter)` and implement all abstract methods

#### Scenario: Core with no adapter loaded

- GIVEN a Core instance with zero adapters configured
- WHEN the system starts
- THEN the system MUST NOT crash
- AND module lifecycle MUST complete normally
- AND `apoch status` MUST report no adapters active

#### Scenario: Adapter start failure does not crash Core

- GIVEN an adapter whose `start()` raises `ConnectionError`
- WHEN `AgentAdapterManager.start_gateway()` is called
- THEN the exception MUST be caught
- AND the adapter MUST be marked as `failed`
- AND the CLI MUST report the failure with the error detail

### Requirement: Module Tool Registration

Modules MUST be able to register their tools with the adapter for MCP exposure. The gateway MUST aggregate all registered tools from all loaded modules.

#### Scenario: Multiple modules register tools

- GIVEN two loaded modules, each providing two tools
- WHEN both modules call `adapter.register_module_tools()` during initialization
- THEN the gateway MUST expose exactly four tools via MCP `tools/list`
- AND each tool MUST include its originating module name in the description

#### Scenario: Module registers duplicate tool name

- GIVEN module A registers tool `record` and module B attempts to register tool `record`
- WHEN `register_module_tools()` is called for module B
- THEN the adapter MUST prefix module B's tool name (e.g., `module_b_record`)
- AND a warning MUST be logged

### Requirement: Gateway Health

The adapter MUST provide health check that verifies the MCP server process is responsive.

#### Scenario: Healthy gateway

- GIVEN the OpenCode adapter is running and accepting requests
- WHEN `adapter.health()` is called
- THEN it MUST return `HealthStatus(healthy=True, uptime_seconds=N)`
- AND `apoch status` MUST show the gateway as healthy

#### Scenario: Gateway process crashed

- GIVEN the MCP gateway process has exited unexpectedly
- WHEN `adapter.health()` is called
- THEN it MUST return `HealthStatus(healthy=False, error="process exited")`
- AND `apoch mcp restart` MUST start a fresh process

#### Scenario: Gateway restart restores health

- GIVEN a crashed gateway process
- WHEN `apoch mcp restart` is executed
- THEN a new process MUST be spawned
- THEN the health check after restart MUST return healthy
- AND previously registered module tools MUST be re-registered

## Error Cases

| Condition | Behavior |
|-----------|----------|
| Adapter process crashes | Health check detects; CLI reports; restart recovers |
| MCP protocol version mismatch | Log mismatch; adapt to supported subset; report in doctor |
| stdio pipe closed unexpectedly | Gateway marked crashed; `apoch mcp restart` recovers |
| Module registers tool after gateway already started | Tool registered dynamically; no restart needed |

## Acceptance Criteria

- [ ] `AgentAdapter` ABC can be subclassed by any agent adapter (OpenCode, Gentle-AI, etc.)
- [ ] Core starts and works with zero adapters
- [ ] OpenCode adapter starts, registers 6+ tools (across all MVP modules), responds to `tools/list`
- [ ] `health()` returns healthy for running gateway, unhealthy for crashed process
- [ ] `apoch mcp restart` fully recovers from crash
- [ ] Tool name collision is handled gracefully (prefix + warning)

## Risks

| Risk | Mitigation |
|------|------------|
| FastMCP API upstream changes | Pin compatible version; wrap in adapter layer |
| stdio buffering issues on Windows | Use unbuffered binary stdio; document Windows quirks |
| Single gateway is crash domain for all modules | v1 intentional; v1.1+ splits per-module processes |

## Future Considerations

- Per-module MCP servers (split gateway for independent lifecycle)
- SSE transport for remote agent communication
- Gentle-AI and other agent adapters via same ABC
- Adapter auto-detection (detect running agent from environment)
