# Architecture Overview

Apoch-AI is an agent-agnostic enhancement framework for AI coding agents. It augments agents with persistent capabilities — project memory, engineering governance, runtime observability, and toolchain integration — that they cannot maintain across sessions.

## Three-Layer Structure

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        MCP PUBLIC API (intentional)                       │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │ apoch_status │  │ apoch_health│  │apoch_history│  │apoch_recommend │ │
│  │ (No params)  │  │ (No params) │  │horas/tipo   │  │ (No params)    │ │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├────────────────┤ │
│  │apoch_progress│  │apoch_insights│  │ apoch_logs  │  │ Legacy Aliases │ │
│  │   periodo    │  │ (No params) │  │nivel/limite │  │ (5 aliases)    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬────────┘ │
│         │                │                │                  │          │
│         └────────────────┴────────────────┴──────────────────┘          │
│                        ApochCoordinator                                  │
│          Orchestrates 6 modules, aggregates responses, builds           │
│          ToolResponse with confidence scoring + evidence                 │
├──────────────────────────────────────────────────────────────────────────┤
│                         CORE STACK (frozen)                              │
│                                                                          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────────┐ │
│  │  StackManager│  │ StackRegistry  │  │  CommandRunner (ABC)         │ │
│  │  Orchestrator│  │ Entry-Point    │  │  ├─ RealRunner (async)       │ │
│  │              │  │ Discovery      │  │  └─ MockRunner (tests)       │ │
│  └──────┬───────┘  └────────────────┘  └──────────────────────────────┘ │
│         │                                                               │
│  ┌──────┴───────┐  ┌────────────────┐  ┌──────────────────────────────┐ │
│  │  StackState  │  │  ComponentInfo │  │  StackDescriptor             │ │
│  │  FSM (11 st) │  │  Detect Data   │  │  Static Metadata             │ │
│  │  derive_state│  │               │  │                              │ │
│  └──────────────┘  └────────────────┘  └──────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│                         CORE MODULES (native)                            │
│                                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐│
│  │  Chronicle │  │  Guardian  │  │   Vision   │  │ Oracle · Pulse      ││
│  │  (Activity)│  │ (Exception)│  │(Observabil)│  │ Optimizer (WIP)     ││
│  └────────────┘  └────────────┘  └────────────┘  └─────────────────────┘│
├──────────────────────────────────────────────────────────────────────────┤
│                         ADAPTER LAYER (pluggable)                        │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   OpenSpec   │  │   Engram     │  │  Context7    │  │  CodeGraph   │ │
│  │  (SDD/Specs) │  │  (Memory)    │  │  (Docs AI)   │  │  (Code KG)   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

## Layers

### MCP Public API (intentional)

The MCP Public API is the primary interface for AI coding agents. Seven tools are exposed through the [Model Context Protocol](https://modelcontextprotocol.io/) via stdio transport.

| Tool | Purpose | Params |
|------|---------|--------|
| `apoch_status` | One-shot system overview | None |
| `apoch_health` | Active problems and severity | None |
| `apoch_history` | Activity timeline | `horas`, `tipo` |
| `apoch_recommend` | Highest-impact next action | None |
| `apoch_progress` | Productivity trends | `periodo` |
| `apoch_insights` | Detected patterns | None |
| `apoch_logs` | Technical debug logs | `nivel`, `limite`, `modulo` |

Each tool is backed by an `ApochCoordinator` method that orchestrates one or more internal modules, aggregates their responses, and builds a standardized `ToolResponse` with confidence scoring, evidence attribution, and error handling.

5 legacy aliases provide backward compatibility for tools previously exposed directly by modules.

See the [MCP Public API Reference](mcp-public-api.md) for complete documentation.

### Core Stack (frozen)

The Core Stack manages third-party developer tooling through a consistent lifecycle interface. It is **frozen** — no architectural changes are allowed. New capabilities arrive only through the Adapter Layer.

| Component | Role |
|-----------|------|
| `StackManager` | Lifecycle orchestrator — install, uninstall, verify, activate, deactivate |
| `StackComponent` | Abstract interface — every adapter implements this contract |
| `StackRegistry` | Component discovery via `importlib.metadata` entry points |
| `ComponentInfo` | Detection data — what `detect()` observes on the local system |
| `ComponentStatus` | Runtime state — descriptor + state + info |
| `StackState` | Finite state machine — 11 states, valid transition table |
| `derive_state()` | Pure function — version comparison drives state derivation |
| `CommandRunner` | Subprocess abstraction — `RealRunner` (production) / `MockRunner` (tests) |

### Adapter Layer (pluggable)

Each adapter wraps a third-party CLI tool. They all implement `StackComponent` following the OpenSpec Reference Component pattern.

| Adapter | Registry ID | Binary | Package | Purpose |
|---------|-------------|--------|---------|---------|
| OpenSpec | `openspec` | `openspec` | `@fission-ai/openspec` (npm) | Spec-Driven Development |
| Engram | `engram` | `engram` | `github.com/Gentleman-Programming/engram` (Go) | Persistent memory |
| Context7 | `context7` | `ctx7` | `ctx7` (npm) | Documentation intelligence |
| CodeGraph | `codegraph` | `codegraph` | `@colbymchenry/codegraph` (npm) | Code knowledge graph |

### Core Modules (native)

Six native modules provide persistent intelligence. Three are stable; three are in development.

| Module | Status | Description |
|--------|--------|-------------|
| Chronicle | ✅ Stable | Activity recording and event timeline (SQLite) |
| Guardian | ✅ Stable | Exception isolation and execution boundaries |
| Vision | ✅ Stable | Observability suite — NDJSON logging, introspection |
| Oracle | ⏳ WIP | Decision analysis and reasoning |
| Pulse | ⏳ WIP | Performance benchmarking and metrics |
| Optimizer | ⏳ WIP | Context and token optimization |

## Key Facts

| Attribute | Value |
|-----------|-------|
| Language | Python 3.13+ |
| Package manager | `uv` |
| CLI framework | `typer` |
| Architecture | Modular, agent-agnostic, three-layer |
| Public API tools | 7 MCP tools + 5 legacy aliases |
| Public API version | `"1.0"` (`API_VERSION`) |
| Methodology | OpenSpec — Spec-Driven Development |
| Target | OpenCode v1, extensible to other agents |
| Core Stack | **Frozen** — no architectural changes permitted |
| Test framework | `pytest` with `asyncio_mode = "auto"` |
| Test doubles | `MockRunner` + `monkeypatch` |
| Linting | Ruff (strict) |
| Stack tests | 361 |
| License | MIT |
| Repository | <https://github.com/guigerdts/Apoch-AI> |
| Current release | v0.9.0-alpha |

## Governance Rules

- **Core Stack is frozen.** No modifications to `StackComponent`, `StackManager`, `StackState`, or `StackRegistry`.
- **All external calls go through `CommandRunner`.** Components never execute subprocesses directly.
- **Adapters follow the OpenSpec Reference Component pattern.** Copy the structure, change only tool-specific logic.
- **Components stay independent.** Zero cross-imports between adapter implementations.
