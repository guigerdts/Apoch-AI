# Apoch-AI

**Engineering Intelligence Layer for AI Coding Agents.**

Apoch-AI is an enhancement framework that augments AI coding agents — OpenCode, Claude Code, Cursor, and others — with persistent capabilities they cannot maintain across sessions: project memory, engineering governance, runtime observability, and toolchain integration.

---

## Features

- **Stack Management** — Install, verify, and manage developer tooling (OpenSpec, Engram, Context7) through a unified CLI.
- **Modular Architecture** — Independent, installable modules that extend your agent without modifying its workflow.
- **Cross-Platform** — macOS, Linux, Windows, WSL, and Termux.
- **Agent-Agnostic** — Works with any AI coding agent. Version 1 targets OpenCode.

---

## Quick Start

```bash
# Install Apoch-AI
pip install apoch-ai

# View available stack components
apoch stack status

# Install all components
apoch stack install

# Verify installations
apoch stack verify
```

---

## CLI Reference

### Global Options

| Flag | Description |
|------|-------------|
| `--version` | Show version and exit |

### `apoch stack` — Component Lifecycle

| Command | Description |
|---------|-------------|
| `apoch stack status` | Show state of all registered components |
| `apoch stack install [components...]` | Install one or all components |
| `apoch stack uninstall [components...]` | Uninstall one or all components |
| `apoch stack verify [components...]` | Verify component installations |

Components are identified by their registry ID: `openspec`, `engram`, `context7`.

### Other Commands

| Command | Description |
|---------|-------------|
| `apoch doctor` | Run system diagnostics |
| `apoch list` | List available components |
| `apoch mcp` | MCP server management |

---

## Components

| Component | Description | Install | Status |
|-----------|-------------|---------|--------|
| **OpenSpec** | Spec-Driven Development for AI assistants | `npm install -g @fission-ai/openspec` | ✅ |
| **Engram** | Persistent memory for AI coding agents | `brew install gentleman-programming/tap/engram` | ✅ |
| **Context7** | Documentation intelligence for AI coding agents | `npm install -g ctx7` | ✅ |

Each component follows the same lifecycle: `detect → install → verify → activate → deactivate → uninstall → health`.

---

## Architecture

Apoch-AI is organized into two layers:

**Core Stack** — A unified CLI (`apoch stack`) that manages third-party developer tools through a consistent lifecycle interface. The Core Stack is frozen and stable.

**Core Modules** — Native Apoch-AI capabilities that provide persistent intelligence:

| Module | Status | Description |
|--------|--------|-------------|
| Chronicle | ✅ | Activity recording and timeline generation |
| Guardian | ✅ | Exception isolation and execution boundaries |
| Vision | ✅ | Observability suite (logging, introspection, metrics) |
| Oracle | ⏳ | Decision analysis and reasoning |
| Pulse | ⏳ | Performance benchmarking |
| Optimizer | ⏳ | Context and token optimization |

---

## Development

- **Language:** Python 3.13+
- **Package Manager:** [uv](https://docs.astral.sh/uv/)
- **Methodology:** [OpenSpec](https://openspec.dev/) — Spec-Driven Development
- **Linting:** Ruff (strict)

### Quick Start (Development)

```bash
uv sync
uv run pytest tests/stack/ -v
```

### Creating a New Adapter

See [Creating a New Adapter](docs/creating-a-new-adapter.md) for the step-by-step guide.

---

## Project Status

**Current release:** `v0.1.0` — Core Stack stable with three adapters.
**Next milestone:** [Ecosystem Adapters](https://github.com/guigerdts/Apoch-AI/milestone/1) — CodeGraph and additional tool integrations.

The Core Stack infrastructure is **frozen**. New components are integration work only — no architectural changes required.

---

## License

MIT
