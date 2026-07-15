# Tasks: Core Stack Installation & Lifecycle

## Global Implementation Rule (NON-NEGOTIABLE)

During `sdd-apply` it is FORBIDDEN to introduce functionality not defined in:
- `PROJECT_MASTER.md`
- `proposal.md` (openspec/changes/core-stack-installation/proposal.md)
- `spec.md` (openspec/specs/core-stack/spec.md)
- `design.md` (openspec/changes/core-stack-installation/design.md)
- `tasks.md` (this file)

If an improvement or new idea emerges during implementation:
- DO NOT implement it.
- DO NOT expand scope.
- DO NOT modify the architecture.
- Document it as an observation for a future change.

Enforcement:
- Each PR MUST end with `ruff check --fix && ruff format` — zero warnings.
- ALL existing tests MUST continue passing.
- Each task MUST be fully completed before starting the next. No partial check-ins.
- NO `TODO`, `FIXME`, `HACK`, temporary code, or partial implementations allowed.
- NO modifying existing behavior unless the task explicitly requires it.
- Any contradiction detected between implementation and `PROJECT_MASTER.md` MUST stop implementation immediately and be reported before continuing.

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

~2000 lines. 3 stacked PRs.

| # | Goal | PR | Test cmd | Harness | Rollback |
|---|------|----|----------|---------|----------|
| 1 | Foundation (phases 1-7) | PR 1 | `pytest -k stack -v -x` | N/A | Revert PR 1 |
| 2 | CLI wiring (phases 8-11) | PR 2 | `pytest -k stack_or_cli -v -x` | `apoch stack status` | Revert PR 2 |
| 3 | Tests (phases 12-15) | PR 3 | `pytest -v && ruff check` | `apoch doctor` | Revert PR 3 |

## Unit 1: Stack Foundation

**Phase 1: Infrastructure Base**
- [ ] 1.1 Create `apoch/stack/__init__.py` + `exceptions.py` (StackError hierarchy).

**Phase 2: Models and Contracts**
- [ ] 2.1 `apoch/stack/state.py` — StackState enum (8 states, FSM transitions).
- [ ] 2.2 `apoch/stack/descriptor.py` — StackDescriptor (name, version, origin).
- [ ] 2.3 `apoch/stack/result.py` — OperationResult (component, operation, duration, errors).
- [ ] 2.4 `apoch/stack/component.py` — StackComponent ABC (detect..health).

**Phase 3: Registry**
- [ ] 3.1 `apoch/stack/registry.py` — StackRegistry via importlib entry_points + tests.

**Phase 4: StackManager**
- [ ] 4.1 `apoch/stack/manager.py` — StackManager (DI: StackRegistry, FileLock, ClockProvider, EventBus) + tests.

**Phase 5: Persistence**
- [ ] 5.1 `apoch/stack/manifest.py` — StackManifest, atomic temp→rename + tests.
- [ ] 5.2 `apoch/stack/paths.py` — StackPaths (config_dir, manifest, lock).

**Phase 6: Locking**
- [ ] 6.1 `apoch/stack/lock.py` — FileLock with timeout, stale detection + tests.

**Phase 7: Events**
- [ ] 7.1 `apoch/stack/events.py` — event name constants + tests.

## Unit 2: Components + CLI

**Phase 8: Clock / CommandRunner / Downloader**
- [ ] 8.1 `apoch/stack/clock.py` — ClockProvider ABC + RealClock + FakeClock + tests.
- [ ] 8.2 `apoch/stack/runner.py` — CommandRunner ABC + RealRunner + MockResult + tests.
- [ ] 8.3 `apoch/stack/downloader.py` — Downloader ABC + RealDownloader + Mock + tests.

**Phase 9: CLI apoch stack**
- [ ] 9.1 `apoch/cli/stack.py` — typer group wrapping StackManager + CliRunner tests.

**Phase 10: Install/Uninstall Integration**
- [ ] 10.1 Modify `apoch/cli/install.py` — install_all() after MCP config.
- [ ] 10.2 Modify `apoch/cli/uninstall.py` — uninstall_all() before backup.

**Phase 11: Doctor Integration**
- [ ] 11.1 Modify `apoch/cli/doctor.py` — add StackManager.health() check.

## Unit 3: Tests + Validation

**Phase 12: CLI Tests**
- [ ] 12.1 Integration: `apoch stack` via CliRunner with mock + `apoch install` consent-gated.

**Phase 13: Integration Tests**
- [ ] 13.1 Full flow: install_all → status → uninstall_all with fakes.
- [ ] 13.2 Rollback at position N (1..4) — verify reverse uninstall.
- [ ] 13.3 State round-trip: write → reload → match.

**Phase 14: Documentation**
- [ ] 14.1 Docstrings on all classes. Update pyproject.toml entry-points.

**Phase 15: Final Validation**
- [ ] 15.1 Validate against PROJECT_MASTER.md §8 (4 components) and §15.
