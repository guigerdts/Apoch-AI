# Apoch-AI

**Engineering Intelligence Layer for AI Coding Agents**

Apoch-AI is an enhancement framework that augments AI coding agents — OpenCode, Claude Code, Cursor, and others — with persistent capabilities they cannot maintain across sessions: project memory, engineering governance, runtime observability, and toolchain integration.

Apoch-AI is **not** a coding agent, an LLM, a model provider, or an IDE. It is a platform that enhances existing agents.

---

## Features

- **Stack Management** — Install, verify, and manage developer tooling (OpenSpec, Engram, Context7, CodeGraph) through a unified CLI.
- **Modular Architecture** — Independent, installable components and native modules that extend your agent without modifying its workflow.
- **Cross-Platform** — macOS, Linux, Windows, WSL, and Termux.
- **Agent-Agnostic** — Works with any AI coding agent. Version 1 targets OpenCode.
- **Spec-Driven Development** — Every feature follows OpenSpec methodology: Proposal → Spec → Design → Tasks → Apply → Verify → Archive.
- **401 Tests** — Comprehensive test suite with MockRunner-based lifecycle testing across all components.

---

## Quick Start

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync

# Check component status
uv run apoch stack status

# Install all components
uv run apoch stack install

# Verify installations
uv run apoch stack verify
```

See [Quick Start Guide](docs/quickstart.md) for a detailed walkthrough.

---

## Architecture

Apoch-AI is organized into two layers:

```
┌─────────────────────────────────────────────────────┐
│                  Core Stack (frozen)                 │
│  StackManager · StackComponent · StackDescriptor    │
│  ComponentInfo · ComponentStatus · StackState       │
│  derive_state() · CommandRunner · StackRegistry     │
├─────────────────────────────────────────────────────┤
│               Adapter Layer (pluggable)              │
│  OpenSpec · Engram · Context7 · CodeGraph            │
├─────────────────────────────────────────────────────┤
│                Core Modules (native)                 │
│  Chronicle · Guardian · Vision (stable)              │
│  Oracle · Pulse · Optimizer (in development)         │
└─────────────────────────────────────────────────────┘
```

See [Architecture Overview](docs/architecture.md) for the full design.

---

## CLI Reference

### Global Options

| Flag | Description |
|------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help |

### Stack Commands

| Command | Description |
|---------|-------------|
| `apoch stack status` | Show state of all registered components |
| `apoch stack install [components...]` | Install one or all components |
| `apoch stack uninstall [components...]` | Uninstall one or all components |
| `apoch stack verify [components...] [--skip-async]` | Verify component installations |

### Other Commands

| Command | Description |
|---------|-------------|
| `apoch status` | Show system health and module statistics |
| `apoch list [--verbose] [--format text\|json]` | List all discovered modules |
| `apoch mcp start\|stop\|restart` | Manage the MCP gateway |
| `apoch doctor` | Run system diagnostics |

See [CLI Reference](docs/cli.md) for complete documentation with examples.

---

## Components

### Stack Adapters

| Component | ID | Description | Install | Tests |
|-----------|----|-------------|---------|-------|
| **OpenSpec** | `openspec` | Spec-Driven Development for AI assistants | `npm install -g @fission-ai/openspec@latest` | 41 |
| **Engram** | `engram` | Persistent memory for AI coding agents | `brew install gentleman-programming/tap/engram` | 48 |
| **Context7** | `context7` | Documentation intelligence for AI coding agents | `npm install -g ctx7` | 36 |
| **CodeGraph** | `codegraph` | Code intelligence knowledge graph | `npm install -g @colbymchenry/codegraph` | 31 |

All adapters follow the same lifecycle: `detect → install → uninstall → verify → activate → deactivate → health`.

See [Adapters Reference](docs/adapters.md) for per-component details.

### Native Modules

| Module | Status | Description |
|--------|--------|-------------|
| **Chronicle** | ✅ Stable | Activity recording and timeline generation |
| **Guardian** | ✅ Stable | Exception isolation and execution boundaries |
| **Vision** | ✅ Stable | Observability suite (logging, introspection, metrics) |
| **Oracle** | ⏳ In development | Decision analysis and reasoning |
| **Pulse** | ⏳ In development | Performance benchmarking |
| **Optimizer** | ⏳ In development | Context and token optimization |

---

## Project Status

**Current release:** `v0.1.0` — Core Stack stable with four adapters and three stable native modules.

**Milestone #1:** Ecosystem Adapters — ✅ Completed (OpenSpec, Engram, Context7, CodeGraph)

The Core Stack infrastructure is **frozen** — no architectural changes will be made. New
components are integration work only, following the [Reference Component Rule](docs/contributing.md#reference-component-rule).

See [Roadmap](docs/roadmap.md) for the full development plan.

---

## Documentation

| User Guide | Developer Guide | Reference |
|------------|-----------------|-----------|
| [Installation](docs/installation.md) | [Architecture](docs/architecture.md) | [Core Stack](docs/core-stack.md) |
| [Quick Start](docs/quickstart.md) | [Development](docs/development.md) | [Adapters](docs/adapters.md) |
| [CLI Reference](docs/cli.md) | [Testing](docs/testing.md) | [Configuration](docs/configuration.md) |
| [FAQ](docs/faq.md) | [Contributing](docs/contributing.md) | [Changelog Policy](docs/changelog-policy.md) |
| [Troubleshooting](docs/troubleshooting.md) | [Release Process](docs/release-process.md) | [Creating a New Adapter](docs/creating-a-new-adapter.md) |

---

## Development

| Requirement | Detail |
|-------------|--------|
| **Language** | Python 3.13+ |
| **Package Manager** | [uv](https://docs.astral.sh/uv/) |
| **Methodology** | [OpenSpec](https://openspec.dev/) — Spec-Driven Development |
| **Linting** | Ruff (strict) |
| **Testing** | pytest + pytest-asyncio + MockRunner |
| **License** | MIT |

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup
git clone https://github.com/guigerdts/Apoch-AI.git
cd Apoch-AI
uv sync

# Run tests
uv run pytest

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
