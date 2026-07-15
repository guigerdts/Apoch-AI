# PR6 — Engram Stack Component Proposal

## Intent
Integrate Engram as the second `apoch stack` component. Apoch does NOT implement Engram — it acts as an adapter to the official project via its public CLI/MCP interface.

Engram is a persistent memory system for AI coding agents: a single Go binary with SQLite + FTS5, exposed via CLI, HTTP API, MCP server, and TUI. Works with any agent that supports MCP.

**Reference Component**: OpenSpec (PR5). Engram follows the exact same structure, lifecycle, and patterns, changing only the adapter-specific logic.

## Core Stack Philosophy (MANDATORY — ALL components)
Apoch does NOT implement any component. It only acts as an adapter to each official project using its public interface. All project-specific information (install command, URLs, version detection, prerequisites) must come from the official project — never hardcoded from assumptions.

## Governance Compliance

| Rule | Status |
|------|--------|
| 1. Core Stack frozen | ✅ No modifications to StackComponent, StackDescriptor, ComponentInfo, ComponentStatus, StackManager, StackState, derive_state(), or CLI |
| 2. CliComponent deferred | ✅ Only 2 adapters exist (OpenSpec + Engram). Not evaluating abstraction yet. |
| 3. PRs bounded | ✅ Target ≤1200 lines per PR. Only adapter + tests + entry point + SDD. |
| 4. Public interfaces only | ✅ Engram public CLI only. No internal files, databases, or undocumented commands. |
| 5. Reference Component Rule | ✅ OpenSpec is the reference. Any structural difference must be justified by a documented Engram limitation. |

## Engram Public Interface (verified against official docs)

Source: https://github.com/Gentleman-Programming/engram (v1.19.0 — Jul 8, 2026)
License: MIT
Installation docs: https://github.com/Gentleman-Programming/engram/blob/main/docs/INSTALLATION.md
Full docs: https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md

| Interface | Details | Source |
|-----------|---------|--------|
| **Homepage** | `https://github.com/Gentleman-Programming/engram` | README |
| **Repository** | `https://github.com/Gentleman-Programming/engram` | README |
| **Docs** | `https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md` | README |
| **CLI binary** | `engram <command>` — single static Go binary, zero dependencies | README |
| **Version** | `engram version` → `engram <semver>` (e.g., `engram 1.19.0`) | Verified locally + docs |
| **Install (macOS/Linux)** | `brew install gentleman-programming/tap/engram` | INSTALLATION.md |
| **Install (Linux)** | Download `engram_<version>_linux_{amd64,arm64}.tar.gz` from GitHub Releases | INSTALLATION.md |
| **Install (Windows)** | `go install github.com/Gentleman-Programming/engram/cmd/engram@latest` or download binary | INSTALLATION.md |
| **Agent setup** | `engram setup opencode` (writes MCP config, no server needed for stdio agents) | README |
| **MCP server** | `engram mcp` (stdio transport, auto-launched by agent) | README |
| **Health check** | `engram doctor` — "Run read-only operational diagnostics" | CLI Reference |
| **Stats check** | `engram stats` — "Memory statistics" | CLI Reference |
| **Data dir** | `~/.engram/` (configurable via `ENGRAM_DATA_DIR`) | INSTALLATION.md |
| **Env vars** | `ENGRAM_DATA_DIR`, `ENGRAM_PORT` (7437), `ENGRAM_PROJECT` | DOCS.md |
| **Requirements** | **None** — static Go binary. Go 1.24+ only needed to build from source. | INSTALLATION.md |

## Engram-Specific Logic (only these differ from OpenSpec)

| Area | OpenSpec (reference) | Engram (this PR) |
|------|---------------------|-------------------|
| **id** | `openspec` | `engram` |
| **kind** | `integrations` | `integrations` |
| **version** | `1.0.0` | `1.19.0` (tracks upstream) |
| **Install method** | `npm` (npm global package) | `homebrew` + binary download (see notes) |
| **Install command** | `npm install -g @fission-ai/openspec@latest` | `brew install gentleman-programming/tap/engram` |
| **Prerequisites** | Node.js >= 20.19.0 | **None** (static Go binary) |
| **Version parser** | `openspec 1.6.0` → `1.6.0` via `r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)"` | `engram 1.19.0` → `1.19.0` via `r"(?:engram\s+)?v?(\d+\.\d+\.\d+)"` |
| **detect() method** | `$PATH` lookup for `openspec` + `--version` | `$PATH` lookup for `engram` + `version` |
| **Health check** | `openspec --help` exit code | `engram doctor` exit code |
| **verify() method** | detect + `openspec --help` smoke test | detect + `engram doctor` smoke test |
| **Activation** | Config session management | `engram setup opencode` or MCP config |
| **Data source** | npm packages in `$NVM_DIR` / `$NODE_PATH` | Go binary + SQLite DB at `~/.engram/` |
| **Homepage URL** | `https://openspec.dev/` | `https://github.com/Gentleman-Programming/engram` |
| **Docs URL** | `https://openspec.dev/docs/` | `https://github.com/Gentleman-Programming/engram/blob/main/DOCS.md` |

### Install method — platform-selected
Engram does NOT have a single universal install command. The official docs document different methods per platform. The adapter MUST select the command dynamically via `platform.system()`:

- **Darwin (macOS)**: `brew install gentleman-programming/tap/engram`
- **Linux**: `curl -fsSL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_linux_$(uname -m).tar.gz | tar -xz` (or Homebrew if available)
- **Windows**: `go install github.com/Gentleman-Programming/engram/cmd/engram@latest`

The DESCRIPTOR's `install_command` field will contain a representative command (Homebrew for macOS/Linux, go install for Windows), but the adapter's `install()` method MUST resolve the command dynamically based on `platform.system()`. The CLI will display the platform-appropriate command.

### Health check
`engram doctor` is the official health/diagnostics command: "Run read-only operational diagnostics". It returns a non-zero exit code on failure. The adapter's `health()` method will call `engram doctor` and parse the exit code only. `engram stats` is NOT a health check — it returns memory statistics, not system health status.

## Files (PR6)

Only adapter-specific files. No Core Stack modifications.

- CREATE `src/apoch/stack/components/engram.py` — EngramComponent (adapter)
- MODIFY `src/apoch/stack/components/__init__.py` — export EngramComponent + DESCRIPTOR
- MODIFY `pyproject.toml` — entry point for engram
- CREATE `tests/stack/components/test_engram.py` — tests
- CREATE `openspec/changes/pr6-engram-component/specs/engram-component.md` — spec
- CREATE `openspec/changes/pr6-engram-component/design.md` — design
- CREATE `openspec/changes/pr6-engram-component/tasks.md` — tasks

## Dependencies
- `apoch.stack` (existing, frozen) — StackComponent ABC, ComponentInfo, StackDescriptor, OperationResult, CommandRunner
- OpenSpec component (reference for structure)

## Risks
- **Engram binary not found** → clear error message, NOT_INSTALLED state
- **Version format changes** → robust regex parser with logging, never crashes
- **engram doctor output changes** → health check parses exit code only, not output text
- **No single universal install command** → Homebrew is primary; adapter logs alternative methods; CLI uses install_command from DESCRIPTOR
- **Go binary not in PATH after Homebrew install** → binary goes to `/usr/local/bin/` — should be discoverable by `shutil.which`
