# CLI Reference

All commands are run via `apoch` (or `uv run apoch` when developing from source).

---

## Global Flags

| Flag | Description |
|------|-------------|
| `--version` | Print version (`0.9.0-alpha`) and exit |
| `--help` | Show help message and exit |

---

## `apoch stack` — Component Lifecycle

Manage installation and verification of third-party CLI tools.

### `apoch stack status`

Show every registered component with its state, detected version, project URLs, and install command.

```
$ uv run apoch stack status

OpenSpec (integrations)
  State:       INSTALLED
  Version:     1.6.0
  Project:     https://openspec.dev/
  Repository:  https://github.com/fission-ai/OpenSpec
  Docs:        https://openspec.dev/docs/
```

States: `INSTALLED` (green), `NOT_INSTALLED` (yellow), `ERROR`/`BROKEN` (red), `OUTDATED` (yellow with installed/required versions).

### `apoch stack install [components...]`

Install one or more components. Defaults to all registered components.

```bash
# Install all
uv run apoch stack install

# Install specific
uv run apoch stack install openspec engram
```

Idempotent — already-installed components are skipped. On failure, previously installed components are rolled back.

Errors:

| Error | Cause |
|-------|-------|
| `Dependency 'X' is not installed` | A required dependency is missing |
| `Installation failed (exit N)` | The package manager returned a non-zero exit code |
| `'X' is not registered` | Component name is not in the registry |

### `apoch stack uninstall [components...]`

Uninstall one or more components. Defaults to all.

```bash
uv run apoch stack uninstall context7
```

Idempotent — already-absent components are skipped. Blocks uninstall if another installed component depends on the target.

### `apoch stack verify [components...] [--skip-async]`

Verify component installations with a two-phase check: detect then run diagnostics.

```bash
# Verify all
uv run apoch stack verify

# Skip long-running remote checks
uv run apoch stack verify --skip-async
```

Each component runs its own verification:

| Component | Verification |
|-----------|-------------|
| OpenSpec | `openspec doctor` |
| Engram | `engram doctor` |
| Context7 | `ctx7 --help` |
| CodeGraph | `codegraph --help` |

A component that passes detection but fails verification transitions to `BROKEN`.

---

## `apoch status` — System Health

Show Apoch-AI version and module discovery counts.

```
$ uv run apoch status
  version:             0.9.0-alpha
  discovered_modules:  6
  loaded_modules:      0
```

| Flag | Description |
|------|-------------|
| `--format text\|json` | Output format (default: `text`) |

---

## `apoch list` — Module Inventory

List all discovered core modules with their name, version, status, and entry point.

```
$ uv run apoch list
  chronicle     0.1.0  unknown   apoch.modules.chronicle.module:ChronicleModule
  guardian      0.1.0  unknown   apoch.modules.guardian.module:GuardianModule
  optimizer     0.1.0  unknown   apoch.modules.optimizer.module:OptimizerModule
  oracle        0.1.0  unknown   apoch.modules.oracle.module:OracleModule
  pulse         0.1.0  unknown   apoch.modules.pulse.module:PulseModule
  vision        0.1.0  unknown   apoch.modules.vision.module:VisionModule
```

| Flag | Description |
|------|-------------|
| `--verbose` | Show entry point path and description |
| `--format text\|json` | Output format (default: `text`) |

---

## `apoch mcp` — MCP Gateway

Start, stop, and restart the MCP (Model Context Protocol) gateway. The gateway connects Apoch-AI modules as tools for the OpenCode agent.

### `apoch mcp start`

```
$ uv run apoch mcp start
✓ MCP gateway started
```

### `apoch mcp stop`

```
$ uv run apoch mcp stop
✓ MCP gateway stopped
```

### `apoch mcp restart`

```
$ uv run apoch mcp restart
✓ MCP gateway restarted
```

---

## `apoch doctor` — Adapter Diagnostics

Run health checks on all registered agent adapters (currently only `opencode`).

```
$ uv run apoch doctor
✓ opencode: healthy (uptime: 124.5s)
```

Exits with code 1 if any adapter is unhealthy.

---

## `apoch install` — Agent Installation

Install Apoch-AI into the OpenCode agent configuration (`opencode.json`). Shows a diff, asks for confirmation, then writes the merged config.

```
$ uv run apoch install
✓ Apoch-AI is already installed in opencode.json
```

If changes are needed, it displays a unified diff and prompts: `Apply these changes? [Y/n]`. After applying, it starts the MCP gateway.

## `apoch uninstall` — Agent Removal

Remove Apoch-AI from OpenCode configuration by restoring `opencode.json` from the last backup.

```
$ uv run apoch uninstall
This will restore opencode.json from the last backup. Continue? [y/N]
```

Defaults to `No` — explicit confirmation required.

---

## `apoch eil` — Engineering Intelligence Layer

Inspect the Engineering Intelligence Layer modules (Pulse, Optimizer, Oracle, Guardian, Chronicle).

### `apoch eil dashboard`

Compact overview of all EIL modules with their state and key metrics.

```
$ uv run apoch eil dashboard
EIL Dashboard
============================================================
  ○ Pulse       not loaded
  ○ Optimizer   not loaded
  ○ Oracle      not loaded
  ○ Guardian    not loaded
  ○ Chronicle   not loaded
```

| Flag | Description |
|------|-------------|
| `--json` | Output in JSON format |

### `apoch eil status`

Detailed module status including registered service keys.

### `apoch eil hypotheses`

List optimization hypotheses from the Optimizer module.

| Flag | Description |
|------|-------------|
| `--limit N` | Max hypotheses to show (default: 10) |
| `--min-confidence F` | Minimum confidence filter 0.0–1.0 (default: 0.0) |
| `--json` | JSON output |

### `apoch eil recs`

List improvement recommendations from the Oracle module.

| Flag | Description |
|------|-------------|
| `--min-priority LEVEL` | Minimum priority: `critical`, `high`, `medium`, `low` (default: `low`) |
| `--limit N` | Max recommendations to show (default: 10) |
| `--json` | JSON output |

### `apoch eil trends`

Show productivity trends from the Pulse module.

| Flag | Description |
|------|-------------|
| `--days N` / `-d N` | Number of days to trend (default: 7) |
| `--json` | JSON output |
