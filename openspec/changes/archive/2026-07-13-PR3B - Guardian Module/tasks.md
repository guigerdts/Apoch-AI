# Tasks: PR3B — Guardian Module

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | force-chained |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: scaffold, diagnostics, entry point | PR3B | `pytest tests/modules/guardian/ -v` | N/A — unit tests only | Revert pyproject.toml + rm `modules/guardian/` |
| 2 | Core: protect logic + Registry wiring | PR3B | `pytest tests/ -k "guardian or registry" -v` | N/A — unit tests only | Revert `registry.py` changes |
| 3 | Tests: protect, diagnostics, Registry integration | PR3B | `pytest tests/modules/guardian/ -v` | `tmp_path` for diagnostics | Revert `tests/modules/guardian/` |

## Phase 1: Foundation

- [ ] 1.1 Create `src/apoch/modules/guardian/__init__.py` — sub-package init with lazy `GuardianModule` export (same pattern as chronicle)
- [ ] 1.2 Create `src/apoch/modules/guardian/diagnostics.py` — `ModuleDiagnostics` frozen dataclass: `module_name: str`, `current_state: str`, `last_error: str | None`, `last_error_traceback: str | None`, `fail_count: int`, `last_failure_time: str | None`
- [ ] 1.3 Create `src/apoch/modules/guardian/module.py` — `GuardianModule(Module)` scaffold with:
  - `__init__(config)`: init in-memory `_diagnostics: dict[str, ModuleDiagnostics]`
  - `start(context)`: log "Guardian started" (no real work — diagnostics store is already initialized)
  - `stop()`: no-op (cleanup not needed for in-memory store)
  - `shutdown()`: inherited no-op
- [ ] 1.4 Register Guardian entry point in `pyproject.toml`: `guardian = apoch.modules.guardian.module:GuardianModule` under `[project.entry-points."apoch.modules"]`

**AC**: GuardianModule loads, state transitions LOADED → RUNNING → STOPPED → SHUTDOWN. Entry point discoverable.

## Phase 2: Core Implementation

- [ ] 2.1 Implement `protect(self, coro, module)` in `GuardianModule`:
  - `await coro` inside try/except
  - On `Exception`: capture `traceback.format_exc()`, store `ModuleDiagnostics`, increment `fail_count`, set `module._state = ModuleState.FAILED`, log warning
  - On success: return the coroutine result as-is
  - Always re-raise `CancelledError` / `asyncio.CancelledError` (don't swallow cancellation)
- [ ] 2.2 Implement diagnostics retrieval API:
  - `diagnostics(module_name) -> ModuleDiagnostics | None` — return entry or None
  - `all_diagnostics() -> dict[str, ModuleDiagnostics]` — return copy of internal dict
  - `clear_diagnostics(module_name) -> None` — delete entry if exists
  - `clear_all_diagnostics() -> None` — clear all entries
- [ ] 2.3 Wire Guardian into `ModuleRegistry`:
  - In `ModuleRegistry.__init__`: add `self._guardian: GuardianModule | None = None`
  - In `ModuleRegistry.load()`: if `name == "guardian"`, store `self._guardian = instance`
  - In `ModuleRegistry.start_all()`: delegate calls to `self._guardian.protect()` for non-Guardian modules
  - In `ModuleRegistry.stop_all()`: delegate calls to `self._guardian.protect()` for non-Guardian modules
  - Guardian's own lifecycle: keep raw try/except (cannot protect itself)

**AC**: Module with broken start() transitions to FAILED via Guardian, Core unaffected. Registry loads Guardian first. Engine unchanged.

## Phase 3: Testing

- [ ] 3.1 Create `tests/modules/guardian/test_guardian.py` — tests for diagnostics:
  - `ModuleDiagnostics` dataclass fields are accessible
  - `diagnostics()` returns None for unknown module
  - `diagnostics()` returns correct data after `protect()` catches exception
  - `all_diagnostics()` returns all entries
  - `clear_diagnostics()` removes entry
  - `clear_all_diagnostics()` clears all entries
- [ ] 3.2 Test `protect()`:
  - `protect()` returns result on successful coroutine
  - `protect()` catches Exception, module transitions to FAILED
  - `protect()` captures last_error and last_error_traceback on failure
  - `protect()` increments fail_count on each failure
  - `protect()` re-raises CancelledError (doesn't swallow)
  - `protect()` does NOT catch BaseException (e.g., KeyboardInterrupt propagates)
- [ ] 3.3 Test Registry integration:
  - Registry loads Guardian first (Guardian appears before other modules in init_order)
  - Registry delegates start_all to Guardian.protect()
  - Registry falls back to raw try/except for GuardianModule itself
  - Module that raises during start() is caught by Guardian, set to FAILED
  - Other modules still start successfully after one module fails
  - Existing registry tests pass with Guardian wired in

**AC**: All tests pass. Full coverage of protect() success/failure paths and Registry integration.

## Summary

| Phase | Tasks | Est. impl lines | Est. test lines | Total |
|-------|-------|----------------|-----------------|-------|
| 1 — Foundation | 4 | 60 | 0 | 60 |
| 2 — Core | 3 | 120 | 0 | 120 |
| 3 — Testing | 3 | 0 | 150 | 150 |
| **Total** | **10** | **180** | **150** | **330** |
