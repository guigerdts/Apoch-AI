# Proposal: Core Stack Installation & Lifecycle

## Intent

Apoch-AI must install and manage four platform components — OpenSpec, Engram, Context7, CodeGraph — as a unified "Core Stack". Zero code exists for this. Users have no way to install, check, or repair the platform tooling Apoch-AI depends on.

## Scope

### In Scope
- `StackComponent` common interface (detect, install, verify, update, uninstall, repair, health)
- `StackRegistry` (extensible, entry-point driven)
- `StackManager` (orchestrator only — no per-component logic)
- `apoch install` auto-installs Core Stack (CLI → Stack, NOT Core → Stack)
- `apoch stack` namespace: `install`, `status`, `uninstall`, `repair`
- Transactional + per-component rollback (Rule 007)
- Common state model (NOT_INSTALLED, INSTALLED, OUTDATED, BROKEN, UNSUPPORTED, INSTALLING, UNINSTALLING, ERROR)
- Persistent state across sessions
- Event emission for all major operations
- Existing installation detection (skip, report)
- Per-component platform availability detection
- Integration with `apoch doctor` (not ModuleRegistry — Stack is independent of Core)

### Out of Scope
- Version upgrades (deferred — `stack update`)
- Remote registry or GUI installer
- Package management beyond `apoch`

## Capabilities

### New Capabilities
- `core-stack`: Core Stack installation, management, and lifecycle

### Modified Capabilities
- `cli-interface`: Add `apoch stack` subcommand namespace; integrate Core Stack into `apoch install`

## Approach

Stack components are external tools (pips, MCP servers, CLIs). Each component implements a **common interface** (`StackComponent`) with uniform lifecycle: `detect()`, `install()`, `verify()`, `update()`, `uninstall()`, `repair()`, `health()`. `StackManager` only **orchestrates** registered components — it never contains OpenSpec, Engram, Context7, or CodeGraph-specific logic.

Components register via a **`StackRegistry`** (extensible, like ModuleRegistry and adapter registry), not hardcoded in StackManager.

Rollback is **per-component + transactional**: each component reverts itself via its own `uninstall()`. StackManager coordinates the reverse sequence on failure.

State model common to all components: `NOT_INSTALLED`, `INSTALLED`, `OUTDATED`, `BROKEN`, `UNSUPPORTED`, `INSTALLING`, `UNINSTALLING`, `ERROR`. Persisted across sessions via state file for real-system detection.

Events emitted for every major operation: `install_started`, `install_completed`, `install_failed`, `uninstall_started`, `uninstall_completed`, `verify_completed`, `repair_completed`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/apoch/cli/` | Modified | Add `stack` group; update `install` (CLI → Stack, NOT Core → Stack) |
| `src/apoch/stack/` | New | StackComponent, StackRegistry, StackManager, state model, events |
| `src/apoch/adapters/registry.py` | Modified | Add `stack.adapters` entry point for StackComponent discovery |
| `src/apoch/cli/doctor.py` | Modified | Stack health checks in `doctor` |
| `pyproject.toml` | Modified | Add `apoch.stack.components` entry point group |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Platform detection misses uncommon OS | Med | Fall back to `unsupported` status |
| Partial install from abrupt kill | Low | Transactional rollback + state file |
| Dependency conflict | Med | Validate prerequisites before any install |

## Rollback Plan

Each `StackComponent` implements its own `uninstall()`. `StackManager` maintains a stack of completed installs in order. On failure: iterate in reverse calling each component's `uninstall()`. State file (`~/.config/apoch/stack-state.json`) records last-known-good state. If rollback fails for a component, log error and report manual cleanup steps. The transaction is atomic at the StackManager level — partial success is never left as the final state.

## Dependencies

- Existing CLI infrastructure (`typer`)
- `uv` / `pip` for Python-component installs
- Platform detection utilities (`apoch._compat`)
- Entry-point groups for StackComponent discovery

## Success Criteria

- [ ] `apoch install` installs all four components on a clean system
- [ ] `apoch stack status` shows correct state per component
- [ ] Failed install mid-sequence rolls back all prior components
- [ ] Re-running detects existing installs and skips them
- [ ] `apoch stack uninstall` removes all components cleanly
- [ ] Unsupported platform shows clear status, no system corruption
- [ ] Core (`apoch/core/`) has zero imports from `apoch/stack/` (Rule 005)
- [ ] Adding a 5th component requires zero changes to StackManager — only a new entry point registration
