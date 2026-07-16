# Apoch-AI

**Engineering Intelligence Layer for AI Coding Agents**

Apoch-AI is an enhancement framework that augments AI coding agents — OpenCode, Claude Code, Cursor, and others — with persistent capabilities they cannot maintain across sessions: project memory, engineering governance, runtime observability, and toolchain integration.

Apoch-AI is **not** a coding agent, an LLM, a model provider, or an IDE. It is a platform that enhances existing agents.

---

## Features

- **Stack Management** — Install, verify, and manage developer tooling (OpenSpec, Engram, Context7, CodeGraph) through a unified CLI.
- **Modular Architecture** — Independent, installable components and native modules that extend your agent without modifying its workflow.
- **Cross-Platform** — macOS, Linux, Windows (WSL), and Termux (Android).
- **Agent-Agnostic** — Works with any AI coding agent. Version 1 targets OpenCode.
- **Spec-Driven Development** — Every feature follows OpenSpec methodology: Proposal → Spec → Design → Tasks → Apply → Verify → Archive.
- **1,156 Tests** (1,148 pass, 8 CI-only skip) — Comprehensive test suite with MockRunner-based lifecycle testing, E2E real-tool validation, and cross-platform CI.

---

## Quick Start

**Minimum requirements:** Python 3.13+, git, and [uv](https://docs.astral.sh/uv/).

> **Termux user?** See the [Termux install guide](docs/installation.md#install-from-source-termux) — `uv` doesn't support Android, so you'll use `pip` instead.

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

### MCP Gateway Commands

| Command | Description |
|---------|-------------|
| `apoch mcp start` | Start the MCP gateway with module tool registration |
| `apoch mcp stop` | Stop the MCP gateway |
| `apoch mcp restart` | Restart the MCP gateway |
| `apoch mcp serve` | Run the MCP gateway (blocking, stdio transport — for OpenCode integration) |

### Engine Intelligence Commands

| Command | Description |
|---------|-------------|
| `apoch status` | Show system health and module statistics |
| `apoch list [--verbose] [--format text\|json]` | List all discovered modules |
| `apoch doctor` | Run system diagnostics |
| `apoch eil status` | Show engine module states |
| `apoch eil hypotheses` | Show optimizer-generated optimization hypotheses |
| `apoch eil recs` | Show oracle strategic recommendations |
| `apoch eil trends` | Show pulse performance trend analysis |

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

| Module | Status | MCP Tools | Description |
|--------|--------|-----------|-------------|
| **Chronicle** | ✅ Stable | 3 tools | Activity recording and timeline generation via SQLite |
| **Guardian** | ✅ Stable | 4 tools | Exception isolation and execution boundaries |
| **Vision** | ✅ Stable | 4 tools | Observability suite (logging, introspection, system info) |
| **Oracle** | ⚡ Functional | — (services) | Decision analysis and recommendation engine |
| **Pulse** | ⚡ Functional | — (services) | Performance telemetry and work-unit tracking |
| **Optimizer** | ⚡ Functional | — (services) | Anomaly detection and code quality analysis |

---

## Project Status

**Current release:** `v0.7.0-alpha` — Core Stack stable with six functional engine modules, E2E test suite, cross-platform CI/CD, and OpenCode MCP integration.

**Milestone #1:** Ecosystem Adapters — ✅ Completed (OpenSpec, Engram, Context7, CodeGraph)

**Milestone #2:** Engine Intelligence Layer — ⚡ 6 modules functional, data ingestion pipeline pending

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
