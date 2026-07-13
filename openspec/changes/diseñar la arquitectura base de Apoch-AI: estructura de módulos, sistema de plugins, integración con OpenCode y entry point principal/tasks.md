# Tasks: Apoch-AI Base Architecture

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1600–1700 over 6 PRs |
| 400-line budget risk | Low (each PR under 400) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Core + Module System + CLI skeleton | PR 1 | `pytest tests/core/ tests/config/ tests/cli/app_test.py` | `apoch list; apoch status` | `git revert` PR 1 — no agent integration |
| 2 | OpenCode Adapter + MCP Gateway | PR 2 | `pytest tests/adapters/ tests/cli/install_test.py` | `apoch install --dry-run` | `git revert` PR 2 + `apoch uninstall` |
| 3 | Core Stack detection | PR 3 | `pytest tests/stack/ tests/cli/config_test.py` | `apoch doctor` | `git revert` PR 3 — detection only |
| 4 | Chronicle module | PR 4 | `pytest tests/modules/chronicle/` | `apoch list` shows chronicle | `git revert` PR 4 |
| 5 | Guardian module | PR 5 | `pytest tests/modules/guardian/` | `apoch status` shows state | `git revert` PR 5 |
| 6 | Vision module | PR 6 | `pytest tests/modules/vision/` | `apoch status --format json` | `git revert` PR 6 |

## PR 1: Core Engine + Module System + CLI Skeleton

- [x] 1.1 RED: core exceptions tests → DoD: red pytest (10/10 failed RED ✅) | Dep: none | Spec: module-system §Error Cases
- [x] 1.2 `pyproject.toml` (uv, entry points `apoch.modules`, `apoch.plugins`, `apoch.cli`) → DoD: `uv pip install -e .` passes ✅ | Dep: none | Spec: cli-interface §Architecture
- [x] 1.3 `src/apoch/__init__.py`, `__main__.py`, `_compat.py` → DoD: `python -m apoch` prints help ✅ | Dep: 1.2 | Spec: cli-interface §Public Interfaces
- [x] 1.4 `core/exceptions.py` (ModuleLoadError, LifecycleError, StateTransitionError, StorageError) → DoD: 10/10 GREEN tests ✅ | Dep: 1.1, 1.3 | Spec: module-system §Error Cases
- [x] 1.5 RED: config loader tests → DoD: red pytest (18/18 failed RED ✅) | Dep: none | Spec: module-system §Config Override
- [x] 1.6 `config/defaults.py` + `config/loader.py` (YAML + APOCH_* env var overlay) → DoD: 20/20 GREEN ✅ | Dep: 1.5, 1.3 | Spec: module-system §Config Override
- [x] 1.7 RED: Module ABC tests → DoD: red pytest (31 FAILED/ERROR ✅) | Dep: none | Spec: module-system §Lifecycle Contract
- [x] 1.8 `core/module.py` (Module ABC, ModuleMetadata, ModuleState, Context) → DoD: 35/35 GREEN ✅ | Dep: 1.7 | Spec: module-system §Public Interfaces
- [x] 1.9 RED: ModuleRegistry tests (25/25 RED → 25/25 GREEN ✅) | Dep: 1.8 | Spec: module-system §Entry Point Discovery
- [x] 1.10 `core/registry.py` (ModuleRegistry — entry point discovery, config filtering, enable/disable) → DoD: 25/25 GREEN ✅ | Dep: 1.9, 1.6 | Spec: module-system §Entry Point Discovery, §Enable/Disable
- [x] 1.11 `core/events.py` (event bus skeleton, publish/subscribe round-trip) → DoD: 14/14 GREEN ✅ | Dep: 1.10 | Spec: module-system §Architecture
- [x] 1.12 `core/engine.py` (Core bootstrap, lifecycle orchestrator, constructor DI, integration start/stop) → DoD: 14/14 GREEN ✅ | Dep: 1.10, 1.6, 1.4 | Spec: module-system §Execution Flow
- [x] 1.13 RED: CLI app tests → DoD: red on `apoch --help` | Dep: none | Spec: cli-interface §List Modules
- [x] 1.14 `cli/app.py` (typer), `cli/list.py`, `cli/status.py` → DoD: `apoch list`, `apoch status` work | Dep: 1.13, 1.12 | Spec: cli-interface §Subcommand Matrix, §List Modules

## PR 2: OpenCode Adapter + MCP Gateway

- [ ] 2.1 RED: AgentAdapter ABC tests → DoD: red pytest | Dep: none | Spec: agent-adapter §Adapter ABC Contract
- [ ] 2.2 `adapters/base.py` (AgentAdapter ABC), `adapters/__init__.py` → DoD: GREEN tests | Dep: 2.1 | Spec: agent-adapter §Public Interfaces
- [ ] 2.3 `plugins/manager.py` (plugin discovery via `apoch.plugins`) → DoD: GREEN tests | Dep: PR 1 | Spec: module-system §In Scope
- [ ] 2.4 RED: MCP server tests → DoD: red on tool registration | Dep: 2.2 | Spec: agent-adapter §Module Tool Registration
- [ ] 2.5 `adapters/opencode/server.py` (FastMCP stdio gateway) → DoD: server starts/tools/list works | Dep: 2.4 | Spec: agent-adapter §Gateway Health
- [ ] 2.6 `adapters/opencode/tools.py` (tool registration, duplicate name prefixing) → DoD: GREEN tests | Dep: 2.5 | Spec: agent-adapter §Module Tool Registration
- [ ] 2.7 RED: opencode.json tests → DoD: red on backup/diff/consent | Dep: none | Spec: cli-interface §Install Module
- [ ] 2.8 `adapters/opencode/config.py` (backup, diff, consent prompt, apply, rollback) → DoD: GREEN tests | Dep: 2.7 | Spec: cli-interface §Execution Flow: apoch install
- [ ] 2.9 `cli/install.py` (install flow with stack detection stubs) → DoD: install backs up + shows diff + asks consent | Dep: 2.8, 2.5 | Spec: cli-interface §Install scenarios
- [ ] 2.10 `cli/uninstall.py` → DoD: restores opencode.json from backup | Dep: 2.8 | Spec: cli-interface §Uninstall
- [ ] 2.11 `cli/mcp.py` (start/stop/restart) → DoD: MCP gateway lifecycle works | Dep: 2.5 | Spec: agent-adapter §Gateway Health
- [ ] 2.12 `cli/doctor.py` (diagnostics checks) → DoD: `apoch doctor` runs checks | Dep: 2.5, 2.11 | Spec: cli-interface §Doctor Diagnostics

## PR 3: Core Stack Detection

- [ ] 3.1 RED: stack detection tests → DoD: red on detect logic | Dep: none | Spec: cli-interface §Doctor Diagnostics
- [ ] 3.2 `stack/detector.py` + `stack/{openspec,engram,context7,codegraph}.py` → DoD: detects each tool (present/absent) | Dep: 3.1 | Spec: cli-interface §Subcommand Matrix
- [ ] 3.3 `cli/config.py` (config get/set/edit) → DoD: `apoch config get` returns value | Dep: PR 1 (config/loader) | Spec: cli-interface §Subcommand Matrix
- [ ] 3.4 Wire stack detection into `apoch install` + `apoch doctor` → DoD: install warns if OpenCode absent | Dep: 3.2, PR 2 | Spec: cli-interface §Install when OpenCode not detected

## PR 4: Module Chronicle

- [ ] 4.1 RED: chronicle tests → DoD: red on record/query/prune | Dep: none | Spec: module-chronicle §Requirements
- [ ] 4.2 `modules/chronicle/module.py` (SQLite-backed record/query/prune, Module ABC) → DoD: GREEN tests (record 10K in <10s) | Dep: 4.1, PR 1 | Spec: module-chronicle §Record, §Query, §Retention
- [ ] 4.3 Wire chronicle tools into MCP gateway → DoD: MCP `chronicle_query` returns JSON list | Dep: 4.2, PR 2 | Spec: module-chronicle §MCP Tool Exposure

## PR 5: Module Guardian

- [ ] 5.1 RED: guardian tests → DoD: red on exception isolation, state machine, timeout | Dep: none | Spec: module-guardian §Requirements
- [ ] 5.2 `modules/guardian/module.py` + `GuardianProxy` in core (exception boundary, state tracking, diagnostics, timeout) → DoD: GREEN tests | Dep: 5.1, PR 1, PR 4 | Spec: module-guardian §Exception Isolation, §State Machine, §Policy Enforcement
- [ ] 5.3 Wire GuardianProxy into Core.start_all/stop_all → DoD: module crash does not crash Core | Dep: 5.2, PR 1 | Spec: module-guardian §Architecture

## PR 6: Module Vision

- [ ] 6.1 RED: vision tests → DoD: red on structured logging, MCP tools | Dep: none | Spec: module-vision §Requirements
- [ ] 6.2 `modules/vision/module.py` (structured JSON logging, log rotation, module state/config inspection, system info) → DoD: GREEN tests | Dep: 6.1, PR 1, PR 5 | Spec: module-vision §Structured Logging, §MCP Tools
- [ ] 6.3 Wire vision tools into MCP gateway → DoD: `vision_state`, `vision_logs`, `vision_system`, `vision_config` all respond | Dep: 6.2, PR 2 | Spec: module-vision §MCP Tools for State Inspection
