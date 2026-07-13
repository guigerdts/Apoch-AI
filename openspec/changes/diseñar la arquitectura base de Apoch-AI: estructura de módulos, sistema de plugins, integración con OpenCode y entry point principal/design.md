# Design: Apoch-AI Base Architecture

## Technical Approach

Modular, agent-agnostic Python framework with CLI-first entry point, entry point-based module discovery, single-process MCP gateway, src-layout, and dependency-inverted core that depends only on ABCs. Six implementation PRs: Core Engine → MCP Gateway → Core Stack → Chronicle → Guardian → Vision.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| **Core Engine** | Event bus vs direct lifecycle hooks | Event bus adds indirection and trace complexity; hooks are simple and predictable | **Direct lifecycle hooks** (`init → start → stop → shutdown`) with optional event bus in Core for future inter-module communication |
| **Module Discovery** | Entry points (`importlib.metadata`) vs config file | Entry points enable pip-installable auto-discovery; config gives explicit control | **Entry points** (`apoch.modules`) as primary + YAML config for disable/override |
| **Plugin vs Module** | Same ABC vs separate API | One concept is simpler; distinct groups prevent namespace collision | **Same `Module` ABC**, separate entry point groups: `apoch.modules` (first-party), `apoch.plugins` (third-party) |
| **MCP Integration** | Single gateway vs per-module servers | Single is simpler to install/manage; per-module gives process isolation | **Single gateway** (`apoch mcp`) for v1, gateway split-able per-module in v1.1+ |
| **CLI Framework** | typer vs click vs argparse | typer has native async + Pydantic validation; click is static; argparse is stdlib but verbose | **typer** (Python 3.13+ native, async support, type hints) |
| **Config Format** | YAML only vs YAML + env vars | YAML supports anchors/comments for file config; env vars enable CI/CD, testing, and automation overrides without file changes | **YAML primary + env var overrides** — YAML for persistent config, `APOCH_*` env vars override on top (e.g., `APOCH_LOG_LEVEL=debug`, `APOCH_HOME=/custom/path`) |
| **Project Layout** | `src/` layout vs flat `apoch/` | src-layout is PEP 517 standard, avoids import ambiguity, is the modern Python packaging norm | **`src/apoch/`** from day one — migration is noise even if "mechanical" |
| **Dependency Injection** | Manual DI vs service locator vs constructor injection | Manual DI is explicit; service locator is global state; constructor injection is testable | **Constructor injection** — Core receives `ModuleRegistry`, `ConfigManager`, `AdapterManager` at init |
| **Exception Boundaries** | try/except wrappers vs context managers vs middleware | Context managers compose naturally; try/except is simplest | **GuardianProxy** — wrapper object per module that intercepts lifecycle calls with timeout + try/except, composition over middleware |

## Data Flow

### Startup Flow

```
apoch ──→ typer CLI app
            │
            ├── ConfigManager.load() ──→ ~/.config/apoch/config.yaml
            ├── Core(config) ──→ ModuleRegistry.discover()
            │                       │
            │                       ├── entry_points(group="apoch.modules") → ModuleMetadata[]
            │                       ├── load(name) → Module instance
            │                       └── start_all(context)
            │                            │
            │                     GuardianProxy wraps each:
            │                       module.init(config) → module.start(ctx)
            │
            ├── AdapterManager.start_gateway()
            │       │
            │       └── OpenCodeAdapter.start() → FastMCP(stdio)
            │             register_module_tools() for each module
            │
            └── Ready ──→ opencode.json: "apoch" → ["apoch", "mcp"]
```

### MCP Request Flow

```
OpenCode Agent ──stdin──→ FastMCP Server ──→ AdapterManager
                    │                            │
                    │                   ModuleRegistry.route_tool(name)
                    │                            │
                    │                   GuardianProxy.protect(module, call)
                    │                            │
                    │                   Module.tool_handler(args)
                    │                            │
                    └──stdout──←── JSON-RPC Response ←── result
```

### Install Flow

```
apoch install ──→ detect OpenCode & opencode.json
                     │
                     ├── backup → ~/.apoch/backups/opencode-{timestamp}.json
                     ├── compute diff → show to user → [Y/n]
                     │
                     ├── [Y] → write opencode.json (add mcpServers.apoch)
                     │       → verify MCP gateway health
                     │       → report success
                     │
                     └── [n] → abort, no changes
```

### Shutdown Flow

```
SIGTERM/SIGINT ──→ Core.stop()
                      │
                      ├── AdapterManager.stop_gateway() → close stdio
                      ├── ModuleRegistry.stop_all()
                      │     GuardianProxy: module.stop() → module.shutdown()
                      └── cleanup temp files / release resources → exit 0
```

## Package Structure

```
src/
└── apoch/
    ├── __init__.py          # version, public exports
    ├── __main__.py          # python -m apoch
    ├── cli/
    │   ├── __init__.py
    │   ├── app.py           # typer app, command tree
    │   ├── install.py       # apoch install
    │   ├── uninstall.py     # apoch uninstall
    │   ├── list.py          # apoch list
    │   ├── status.py        # apoch status
    │   ├── mcp.py           # apoch mcp {start|stop|restart}
    │   ├── config.py        # apoch config {get|set|edit}
    │   └── doctor.py        # apoch doctor
    ├── core/                # CORE — depends on nothing external
    │   ├── __init__.py
    │   ├── engine.py        # Core bootstrap, lifecycle orchestrator
    │   ├── module.py        # Module ABC
    │   ├── registry.py      # ModuleRegistry
    │   ├── events.py        # Optional event bus skeletons
    │   └── exceptions.py    # Domain exceptions
    ├── adapters/            # Agent adapters — implement AgentAdapter ABC
    │   ├── __init__.py
    │   ├── base.py          # AgentAdapter ABC
    │   └── opencode/
    │       ├── __init__.py
    │       ├── server.py    # FastMCP stdio gateway
    │       ├── tools.py     # Tool registration helper
    │       └── config.py    # opencode.json read/write
    ├── plugins/
    │   ├── __init__.py
    │   └── manager.py       # Plugin discovery (apoch.plugins)
    ├── modules/             # First-party modules
    │   ├── __init__.py
    │   ├── chronicle/module.py
    │   ├── guardian/module.py
    │   └── vision/module.py
    ├── stack/               # Core stack detection & management
    │   ├── __init__.py
    │   ├── detector.py      # Stack detection
    │   ├── openspec.py
    │   ├── engram.py
    │   ├── context7.py
    │   └── codegraph.py
    ├── config/
    │   ├── __init__.py
    │   ├── loader.py        # YAML config load/merge + env var overlay
    │   └── defaults.py      # Default config values
    └── _compat.py           # Cross-platform (signal, path, encoding)
```

All new files — greenfield project.

## Interfaces / Contracts

### Module ABC

```python
class Module(ABC):
    metadata: ModuleMetadata  # name, version, description

    def __init__(self, config: dict) -> None: ...
    async def start(self, context: Context) -> None: ...
    async def stop(self) -> None: ...
    async def shutdown(self) -> None: ...
```

### AgentAdapter ABC

```python
class AgentAdapter(ABC):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> HealthStatus: ...
    async def register_module_tools(self, name: str, tools: list[ToolDef]) -> None: ...
```

### Key Types

```python
@dataclass
class ModuleMetadata:
    name: str; version: str; description: str; entry_point: str

@dataclass
class ToolDef:
    name: str; description: str; input_schema: dict

@dataclass
class HealthStatus:
    healthy: bool; uptime_seconds: float | None; error: str | None

class ModuleState(Enum):
    LOADED, RUNNING, STOPPED, SHUTDOWN, FAILED = ...
```

### Public API (`apoch/__init__.py`)

```python
__version__ = "0.1.0"
__all__ = ["core", "cli", "adapters", "modules", "plugins", "stack", "config"]
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Module ABC conformance | pytest + ABCMeta validation |
| Unit | Config loader (YAML parse, merge, fallback) | TempDir + fixture YAML files |
| Unit | CLI command parsing | typer CliRunner |
| Unit | opencode.json backup/restore/revert | in-memory JSON + file assertions |
| Unit | Guardian state machine & timeout | MockModule with controlled delays |
| Integration | ModuleRegistry discover() + lifecycle | In-memory registry with test entry points |
| Integration | MCP gateway with mock modules | FastMCP test client over stdio mock |
| Integration | Install flow (backup → diff → consent → apply) | TempDir + mock stdio |

## Threat Matrix

N/A — No routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary changed by this design. CLI uses typer (direct argument dispatch), MCP uses stdio JSON-RPC (no shell injection surface for v1). Future per-module subprocess isolation would re-trigger this assessment.

## Migration / Rollout

No migration required — greenfield project. Implementation in six independent PRs, each with a single responsibility:

| PR | Scope | Lines (est.) | Risk |
|----|-------|-------------|------|
| **PR 1** | Core Engine + Module System + CLI skeleton | ~400 | Low — foundational, no agent integration |
| **PR 2** | OpenCode Adapter + MCP Gateway + opencode.json management | ~350 | Medium — stdio MCP protocol correctness |
| **PR 3** | Core Stack (OpenSpec, Engram, Context7, CodeGraph detection) | ~200 | Low — detection logic, no runtime dependency |
| **PR 4** | Module: Chronicle (activity recording, timeline, storage) | ~250 | Medium — SQLite persistence |
| **PR 5** | Module: Guardian (exception boundaries, scope protection) | ~200 | Medium — timeout/interrupt handling |
| **PR 6** | Module: Vision (observability, structured logging, context inspection) | ~200 | Low — logging wrapper with structured output |

## Open Questions

- [ ] FastMCP vs custom minimal MCP implementation — evaluate dependency weight tradeoff
- [ ] How to handle Guardian's own timeouts without importing asyncio in the ABC layer — use `contextvars`?
