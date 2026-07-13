# Proposal: PR3B — Guardian Module

## Intent

Protect the Apoch-AI Core from misbehaving modules by wrapping lifecycle calls in exception boundaries and capturing structured diagnostics. The Registry currently has inline try/except — PR3B formalises this into a dedicated Guardian module that provides reusable, observable protection for every module lifecycle call.

## Scope

### In Scope
- `GuardianModule(Module)` — itself a Module, follows the same lifecycle as any other
- `protect(coro, module_name)` — wraps any async lifecycle call in try/except; on exception captures diagnostics and transitions the module to `FAILED`
- `diagnostics(module_name)` / `all_diagnostics()` / `clear_diagnostics()` — structured diagnostics retrieval
- `ModuleDiagnostics` dataclass: module_name, current_state, last_error, last_error_traceback, fail_count, last_failure_time
- Wire Guardian into `ModuleRegistry` lifecycle calls (`start_all`, `stop_all`) — replace inline try/except with `Guardian.protect()`
- Guardian entry point registration in `pyproject.toml`

### Out of Scope
- Configurable timeouts per lifecycle call (deferred to future resilience PR)
- Policy framework / `set_policy()` (deferred)
- Chronicle integration for audit logging (deferred — Python `logging` only for PR3B)
- Vision integration (deferred)
- MCP tools (deferred)
- Disk persistence (diagnostics in memory only)
- Uptime tracking (deferred)
- Modifying Chronicle, Vision, Adapters, or CLI

## Capabilities

### Modified Capabilities
- `module-guardian`: PR3B implements exception isolation and diagnostics only — a strict subset of the full spec. Timeouts, policy enforcement, Chronicle/Vision integration, and MCP tools are deferred.

## Approach

`GuardianModule` stores an in-memory `dict[str, ModuleDiagnostics]`. Its `protect()` wraps an awaitable with try/except: on success the module runs normally; on exception it captures the error type, message, traceback (`traceback.format_exc()`), increments `fail_count`, and records the module's current state. The `ModuleRegistry` already has inline try/except — refactor to delegate `start()` and `stop()` calls through `Guardian.protect()`. Guardian itself cannot protect its own lifecycle; the Registry handles `GuardianModule.start()` with a raw try/except fallback.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/apoch/modules/guardian/` | New | Module + diagnostics |
| `pyproject.toml` | Modified | Register guardian entry point |
| `tests/modules/guardian/` | New | Test suite |
| `src/apoch/core/registry.py` | Modified | Delegate to Guardian.protect() |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Registry refactoring breaks existing module lifecycle | Low | Keep raw try/except as fallback path; chronicle integration tests must pass |
| Guardian fails during its own start() | Low | Raw try/except in registry for Guardian specifically |

## Rollback Plan

Revert `registry.py`, remove `modules/guardian/`, revert `pyproject.toml`, remove `tests/modules/guardian/`. All other modules (Chronicle, Engine, CLI) remain intact.

## Dependencies

Python stdlib only (`traceback`, `logging`, `dataclasses`). No new external dependencies.

## Success Criteria

- [ ] Exception in `module.start()` is caught by Guardian, module transitions to `FAILED`, Core unaffected
- [ ] `guardian.diagnostics("chronicle")` returns error type, message, traceback, and `fail_count >= 1` after a failure
- [ ] `guardian.all_diagnostics()` returns correct state for all loaded modules
- [ ] Invalid state transitions still rejected by Module ABC (Guardian does NOT bypass state machine)
- [ ] All existing tests pass (test_registry.py, test_module.py, tests/modules/chronicle/)
- [ ] Core does NOT import from `modules/` — Clean Architecture intact
