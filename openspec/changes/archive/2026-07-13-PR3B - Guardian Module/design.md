# Design: PR3B — Guardian Module

## Technical Approach

`GuardianModule` is itself a Module (follows Module ABC lifecycle). It stores diagnostics in-memory and exposes `protect()` to wrap lifecycle calls with exception boundaries. `ModuleRegistry` loads Guardian first during init, stores a reference, and delegates all subsequent lifecycle calls through `Guardian.protect()`. Engine remains unchanged — it only talks to `ModuleRegistry`.

Spec: `module-guardian` (PR3B subset: exception isolation + diagnostics only).

## Architecture Decisions

### Decision: Guardian as Module with Registry injection

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Guardian in `core/` (internal service) | Breaks module pattern, hard to version | ❌ |
| GuardianModule in `modules/`, Engine passes to Registry | Engine knows Guardian — violates constraint | ❌ |
| GuardianModule discovered and loaded first by Registry | Engine unchanged, Core doesn't import modules, DI preserved | ✅ |

**Rationale**: Registry discovers and loads Guardian via entry points like any other module, but stores an internal reference. For all subsequent modules, Registry delegates lifecycle calls to `Guardian.protect()`. Guardian's own lifecycle uses raw try/except (cannot protect itself).

### Decision: Diagnostics only in memory

| Option | Tradeoff | Decision |
|--------|----------|----------|
| SQLite or JSON persistence | Adds complexity, couples to Chronicle patterns | ❌ |
| In-memory dict | Simplest, no new deps, extensible later | ✅ |

**Rationale**: Diagnostics survive module restarts within the same process. Disk persistence can be added as a wrapper later without changing the interface.

### Decision: `protect()` receives the Module instance

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `protect(coro, module_name)` — Guardian has no module ref | Can't set FAILED state on module | ❌ |
| `protect(coro, module: Module)` | Full control; follows existing `mod._state = FAILED` pattern in registry.py | ✅ |

### Decision: Reuse existing `ModuleState` from `core/module.py`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| New state machine in Guardian | Duplication, desync risk | ❌ |
| Use `ModuleState` from core | Single source of truth, no drift | ✅ |

## Data Flow

```
Engine.start()
  │
  └── Registry.discover() ──→ [chronicle, guardian, vision, ...]
  │
  └── Registry.load("guardian") ──→ GuardianModule instance
  │     Store self._guardian reference
  │
  └── Registry.load("chronicle") ──→ ChronicleModule instance
  │
  └── Registry.start_all(context)
        │
        ├── GuardianModule.start()  ──→ raw try/except (Guardian can't protect itself)
        │
        └── ChronicleModule.start() ──→ Guardian.protect(chronicle.start(), chronicle)
              │                            │
              │                      [success] ─→ RUNNING
              │                      [exception] ─→ FAILED + diagnostics captured
              │
              └── (repeat for every other module)

Engine.stop()
  │
  └── Registry.stop_all()
        │
        ├── other modules stop ──→ Guardian.protect(module.stop(), module)
        └── GuardianModule.stop() ──→ raw try/except
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/guardian/__init__.py` | Create | Package init, lazy-export `GuardianModule` |
| `src/apoch/modules/guardian/diagnostics.py` | Create | `ModuleDiagnostics` dataclass (module_name, current_state, last_error, last_error_traceback, fail_count, last_failure_time) |
| `src/apoch/modules/guardian/module.py` | Create | `GuardianModule(Module)` — `protect()`, `diagnostics()`, `all_diagnostics()`, `clear_diagnostics()` |
| `pyproject.toml` | Modify | Register `guardian = apoch.modules.guardian.module:GuardianModule` |
| `src/apoch/core/registry.py` | Modify | Load Guardian first, store reference, delegate lifecycle to `Guardian.protect()` |
| `tests/modules/guardian/__init__.py` | Create | Test package init |
| `tests/modules/guardian/test_guardian.py` | Create | Tests for Guardian |

## Interfaces / Contracts

```python
# diagnostic
@dataclass
class ModuleDiagnostics:
    module_name: str
    current_state: str         # ModuleState value (LOADED, RUNNING, STOPPED, SHUTDOWN, FAILED)
    last_error: str | None     # "TypeError: ..."
    last_error_traceback: str | None  # traceback.format_exc()
    fail_count: int
    last_failure_time: str | None     # ISO 8601

# module
class GuardianModule(Module):
    async def protect(self, coro: Awaitable, module: Module) -> Any:
        """Wrap *coro* in try/except. On exception, capture diagnostics,
        set module._state = FAILED, log. Returns None on failure."""
        ...

    def diagnostics(self, module_name: str) -> ModuleDiagnostics | None: ...
    def all_diagnostics(self) -> dict[str, ModuleDiagnostics]: ...
    def clear_diagnostics(self, module_name: str) -> None: ...
```

## Registry Integration

```python
# In ModuleRegistry.__init__:
self._guardian: GuardianModule | None = None

# In ModuleRegistry.load(name):
instance = module_class(config=module_config)
if name == "guardian":
    self._guardian = instance  # store reference

# In ModuleRegistry.start_all:
if self._guardian and mod is not self._guardian:
    await self._guardian.protect(mod.start(context), mod)
else:
    # Raw try/except for Guardian itself (or no Guardian configured)
    ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit — GuardianModule | `protect()` catches exception, captures diagnostics, sets FAILED state | Mock Module, verify diagnostics fields |
| Unit — diagnostics | `diagnostics()`, `all_diagnostics()`, `clear_diagnostics()` | Direct calls after simulated failure |
| Unit — Registry integration | Guardian intercepts lifecycle calls, FAILED on exception | Real GuardianModule + mock modules |
| Integration | Full start_all → module fails → diagnostics available | `tmp_path` no isolation needed (in-memory) |
| Regression | Existing tests pass with Guardian wired in | `test_registry.py`, `test_chronicle` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary in this change.

## Migration / Rollout

No migration required. Guardian is additive — existing modules continue to work. If Guardian fails to load, Registry falls back to inline try/except.

## Estimated Size

~250–350 changed lines:
- Guardian module: 120–150 lines
- Diagnostics: 20 lines
- Registry changes: 20 lines
- pyproject.toml: +1 line
- Tests: 100–150 lines

## Architecture Risks

| Risk | Mitigation |
|------|------------|
| Guardian fails during start, no protection for other modules | Registry falls back to raw try/except |
| Registry refactoring breaks existing lifecycle | Start_all/stop_all keep raw try/except as fallback path |
| `mod._state` direct mutation is fragile | Same pattern already used in Registry line 120 |

## Acceptance Criteria

- [ ] `GuardianModule` is a proper `Module` subclass (LOADED → RUNNING → STOPPED → SHUTDOWN)
- [ ] `protect()` catches any Exception from the wrapped coroutine
- [ ] On exception: module transitions to `FAILED`, diagnostics captured, exception does NOT propagate
- [ ] `diagnostics("chronicle")` returns `ModuleDiagnostics` with error details after failure
- [ ] `all_diagnostics()` returns correct state for all loaded modules
- [ ] `clear_diagnostics()` resets diagnostics for a specific module
- [ ] Registry.start_all delegates to Guardian.protect for non-Guardian modules
- [ ] Registry falls back to raw try/except for GuardianModule itself
- [ ] All existing tests pass unchanged
- [ ] Core does NOT import from `modules/`
- [ ] Engine unchanged — no reference to GuardianModule

## Open Questions

None.
