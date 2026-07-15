# Core Stack Specification

## Purpose

Unified lifecycle for four platform components (OpenSpec, Engram, Context7, CodeGraph) with extensible discovery, transactional rollback, and cross-platform support. Core MUST NOT depend on Stack (Rule 005).

## Architecture

Dependency: CLI → Stack → Integrations. Stack is NOT in ModuleRegistry.

| Component | Role |
|-----------|------|
| StackManager | Orchestrator, zero per-component logic |
| StackRegistry | Entry-point discovery (`apoch.stack.components`) |
| StackComponent | Common interface: detect, install, verify, activate, deactivate, uninstall, health |
| StackState | FSM: UNKNOWN, NOT_INSTALLED, INSTALLING, INSTALLED, ACTIVE, INACTIVE, OUTDATED, UNSUPPORTED, BROKEN, ERROR, REMOVED |

## Requirements

### Requirement: StackComponent Interface

| Method | Returns | Behavior |
|--------|---------|----------|
| detect() | ComponentInfo | Factual observation: installed, version, available_version, executable_path, metadata |
| install() | OperationResult | Install the component via official command |
| verify() | OperationResult | Validate installation (detect → derive_state → integrity) |
| activate() | OperationResult | Make available for session |
| deactivate() | OperationResult | Disable without uninstalling |
| uninstall() | OperationResult | Remove component via official command |
| health() | dict | Functional check — does it actually work? |

### Requirement: Component Versioning

Each StackComponent MUST expose:
- `name`: unique component identifier
- `installed_version`: currently installed version, or None
- `available_version`: latest available version, or None
- `origin`: installation source (pypi, uv, git, binary, mcp, local)
- `min_apoch_version`: minimum Apoch-AI version required

Version metadata is part of `detect()` and `health()` output — never inferred from file presence alone.

### Requirement: StackRegistry

StackRegistry SHOULD allow declaring dependencies between components. Current install order is fixed (OpenSpec → Engram → Context7 → CodeGraph). Future releases MUST resolve order automatically via a dependency graph without modifying StackManager.

Discover components via `apoch.stack.components` entry points in `pyproject.toml`, using `importlib.metadata` at startup. New component = new entry point only — zero changes to StackManager.

### Requirement: StackManager Orchestration

Orchestrates in registration order. Zero per-component logic.

#### Scenario: Full install sequence

- GIVEN a clean system, no components installed
- WHEN install_all() runs
- THEN each component installs in order, verify() after each
- AND events emit per stage

#### Scenario: Skip already-installed

- GIVEN some components already INSTALLED
- WHEN install_all() runs
- THEN detect() runs first per component
- THEN INSTALLED ones are skipped with report

### Requirement: Install Flow

detect() → if missing: install() → verify(). On failure: reverse rollback.

#### Scenario: Full install success

- GIVEN all four components NOT_INSTALLED
- WHEN `apoch install` or `apoch stack install` runs
- THEN all reach INSTALLED state
- AND events: install_started → install_completed → verify_completed(ok)

#### Scenario: Mid-sequence rollback

- GIVEN three of four installed successfully
- WHEN the fourth install() fails
- THEN StackManager rolls back in reverse order
- AND no partial success remains

### Requirement: Uninstall Flow

Reverse registration order. Each runs uninstall(). State file removed after all succeed.

### Requirement: Integrity Verification

After every install, update, or repair operation the system MUST run `verify()` on the affected component. If `verify()` fails:
- The component transitions to BROKEN state
- The parent operation (install/repair) is considered FAILED
- Transactional rollback applies when the operation is part of an install/update sequence

Install flow becomes: detect() → if missing: install() → **verify()** → if verify fails: rollback.

### Requirement: Repair Flow

detect() all → identify BROKEN → repair() each → verify() each. Emit repair_completed.

### Requirement: Transactional Rollback

Each component self-uninstalls. StackManager tracks order, reverses on failure. Atomic — no partial success.

### Requirement: State Persistence

State at `~/.config/apoch/stack-state.json`. Detect real state each run (not cached). Corrupted: warn, reset to NOT_INSTALLED.

### Requirement: StackManifest

A `StackManifest` document MUST represent the complete, authoritative state of the Core Stack at any point in time. It MUST be reconstructible after restarting Apoch.

The manifest includes per-component: name, installed_version, state, health, last_verified_at, origin. No implicit states — every component must have an explicit entry.

### Requirement: Atomic Persistence

All persistent state modifications MUST occur ONLY after the operation completes successfully. Never write partial manifests. Use atomic file writes (write to temp → rename) for all state file mutations. If Apoch crashes mid-operation, the on-disk manifest reflects the last known-good state.

### Requirement: Events

| Event | Payload |
|-------|---------|
| install_started/completed/failed | name [, reason] |
| uninstall_started/completed | name |
| verify_completed | name, status |
| repair_completed | name, status |

### Requirement: Structured Operation Results

Every StackManager operation MUST return an `OperationResult` with:

| Field | Description |
|-------|-------------|
| component | Target component name |
| operation | install / update / uninstall / repair |
| duration_seconds | Wall-clock duration |
| result | success / partial / failed |
| rollback_executed | true/false |
| errors | List of error messages (empty if none) |
| warnings | List of warning messages (empty if none) |
| component_state | Final StackState per component |

CLI SHALL use OperationResult directly for display — never infer state.

### Requirement: Error Handling

Per-component errors never crash others. StackManager catches + rolls back. State → ERROR on unrecoverable. Messages include remediation.

### Requirement: Operation Locking

Only one Stack operation MAY be active at a time. StackManager MUST acquire a lock (e.g., file lock on `~/.config/apoch/stack.lock`) before executing any mutating operation (install, update, uninstall, repair). If lock is held, subsequent operations SHALL fail with a clear error message naming the active operation. Lock MUST be released on completion or failure.

### Requirement: Cross-Platform

OpenSpec on all platforms (Linux, macOS, Windows, WSL2, Termux). Others detect availability. Unsupported: report, never corrupt.

### Requirement: Future Component Types

StackManager MUST support heterogeneous component types without modification. The StackComponent interface SHALL be implementable for:
- Git repositories
- PyPI packages (uv install)
- Binary downloads
- MCP servers
- Local file-based installations

StackManager orchestrates via the interface only — it never knows the concrete installation method. A new component type = a new StackComponent implementation + entry point registration.

### Testing

Unit: StackManager (mocked components) + each component in isolation. Integration: real detect/install, rollback at each position, state file persistence.
