# Exploration: PR3A - Chronicle Foundation

## Current State

The Apoch-AI framework has a working core (Module ABC, Registry, Engine, EventBus, ConfigLoader, CLI) but **zero concrete modules**. The `src/apoch/modules/` directory does not exist yet. The `__init__.py` already references `modules` in `__all__`. The entry-point group `apoch.modules` in `pyproject.toml` is a commented-out placeholder.

The Chronicle spec (`openspec/specs/module-chronicle/spec.md`) is well-defined with requirements, error cases, and interfaces. The module-system infrastructure (state machine, lifecycle validation, registry with discovery+load+start) is production-ready.

## Affected Areas

| Path | Why |
|------|-----|
| `src/apoch/modules/` | **Does not exist** — needs to be created as the modules package |
| `src/apoch/modules/__init__.py` | New — package init, exports |
| `src/apoch/modules/chronicle/__init__.py` | New — sub-package init |
| `src/apoch/modules/chronicle/module.py` | New — `ChronicleModule(Module)` |
| `src/apoch/modules/chronicle/storage.py` | New — `SqliteEventStore` |
| `src/apoch/modules/chronicle/models.py` | New — `ActivityEvent` dataclass |
| `src/apoch/_compat.py` | Extend — add `user_data_dir()` for XDG_DATA_HOME |
| `pyproject.toml` | Edit — uncomment and fill `chronicle` entry point |
| `tests/modules/chronicle/` | New — test directory for Chronicle |
| `tests/modules/chronicle/test_module.py` | New — lifecycle tests |
| `tests/modules/chronicle/test_storage.py` | New — SQLite storage tests |
| `openspec/specs/module-chronicle/spec.md` | Already exists — no changes needed |

## Approaches

### Q1: Module Package Structure

**Current state**: `src/apoch/modules/` is referenced in `__init__.py.__all__` but doesn't exist. The package finder (`tool.setuptools.packages.find`) includes `apoch*` so it will auto-discover any new sub-packages.

**Recommended approach**: Create standard namespace layout:

```
src/apoch/modules/
├── __init__.py         # "Apoch-AI first-party modules."
├── chronicle/
│   ├── __init__.py     # Public exports: ChronicleModule, ActivityEvent
│   ├── module.py       # ChronicleModule(Module) — lifecycle + public API
│   ├── storage.py      # SqliteEventStore — all SQLite operations
│   └── models.py       # ActivityEvent dataclass, EventFilter, EventStats
```

- **Pros**: Standard Python package layout, clean separation of concerns, scalable to future modules
- **Cons**: Slightly more files than a flat module
- **Effort**: Low

**Alternatives considered**: Single flat file `chronicle.py` in `src/apoch/`. Rejected because it conflates lifecycle, storage, and models in one file — won't scale beyond v1.

### Q2: ChronicleModule Connection to Module ABC

**Current state**: `Module(ABC, _StateMachine)` provides `__init__(config)`, `_state`, `_transition()`, and abstract `start(context)`, `stop()`, `shutdown()`. Lifecycle validation is injected via `__init_subclass__`. Subclasses never need to call `super()`.

**Recommended approach**: ChronicleModule **extends Module directly** — no additional state wrapping.

```python
class ChronicleModule(Module):
    async def start(self, context: Context) -> None:
        self._store = SqliteEventStore(self._resolve_db_path())
        await self._store.initialize()

    async def stop(self) -> None:
        await self._store.close()

    async def shutdown(self) -> None:
        self._store = None
```

- **Pros**: Zero duplication — Module ABC already handles state transitions and lifecycle validation; `_validate_lifecycle` decorator is injected automatically
- **Cons**: None — this is exactly what Module ABC was designed for
- **Effort**: Low

**Alternatives considered**: Adding internal state machine wrapping or manual `_transition()` calls inside chronicle methods. Rejected — that would duplicate what Module ABC already provides via `_pre_start`, `_pre_stop`, `_pre_shutdown` hooks.

### Q3: SQLite Approach

**Current state**: No storage code exists yet. The project depends only on stdlib + MCP + Pydantic + PyYAML + Typer.

**Recommended approach**: Single `SqliteEventStore` class using stdlib `sqlite3` with WAL mode. No ABC in v1.

```python
class SqliteEventStore:
    """SQLite-backed event store. WAL mode, microsecond precision."""
    
    def __init__(self, db_path: Path) -> None: ...
    async def initialize(self) -> None: ...       # Create tables, enable WAL
    async def record(self, event: ActivityEvent) -> None: ...
    async def query(self, filter: EventFilter) -> list[ActivityEvent]: ...
    async def prune(self, before: datetime) -> int: ...
    async def stats(self) -> EventStats: ...
    async def close(self) -> None: ...
```

- **Pros**: Zero additional dependencies, stdlib `sqlite3` is mature and well-tested; WAL mode handles concurrent access; single class is easy to test and maintain
- **Cons**: Tied to SQLite — swapping backends requires refactoring (but we accept that for v1)
- **Effort**: Low

**Alternatives considered**: Repository pattern with an ABC `EventStore` and `SqliteEventStore` implementation. Rejected for v1 because YAGNI — if/when a second backend arrives, the extraction is mechanical and the `SqliteEventStore` method signatures serve as the implicit interface.

### Q4: Data Directory Resolution

**Current state**: `_compat.py` has `user_config_dir()` (XDG_CONFIG_HOME) and `apoch_home()` (`~/.apoch` or `$APOCH_HOME`). Neither follows XDG_DATA_HOME (`~/.local/share`), which is the spec's target.

**Recommended approach**: Add `user_data_dir()` to `_compat.py`:

```python
def user_data_dir() -> Path:
    """Return the platform-appropriate Apoch-AI data directory.
    
    Uses XDG_DATA_HOME (Linux/macOS) or %APPDATA% (Windows).
    Override via $APOCH_DATA or $APOCH_HOME.
    """
    env = os.environ.get("APOCH_DATA") or os.environ.get("APOCH_HOME")
    if env:
        return Path(env)
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "apoch"
```

Chronicle resolves its DB path as `config.get("db_path") or user_data_dir() / "chronicle.db"`.

- **Pros**: Follows XDG spec; reusable by future modules; data and config stay separate; environment overrides available
- **Cons**: Adds one more helper to `_compat.py`
- **Effort**: Low

**Alternatives considered**: Let Chronicle resolve its own path internally. Rejected because `_compat.py` is the designated place for platform-aware path resolution — other modules will need the same.

### Q5: ActivityEvent Schema

**Current state**: Spec defines `{id, timestamp, type, source, severity, payload}`.

**Recommended approach**:

```python
@dataclass(frozen=True)
class ActivityEvent:
    id: str                           # UUID string
    timestamp: datetime               # Timezone-aware, microsecond precision
    type: str                         # e.g. "lifecycle", "tool_invocation", "error", "warning", "user_action"
    source: str                       # e.g. "chronicle", "engine", "guardian"
    severity: str                     # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    payload: dict | None = None       # JSON-serializable dict
```

- **Pros**: Frozen dataclass is immutable, hashable, serializable; all spec fields covered; UUID avoids auto-increment issues across backends
- **Cons**: UUIDs are slightly larger than integer IDs (irrelevant for v1 scale)
- **Effort**: Low

**What was NOT added**: `session_id` (multi-session correlation — v1.1), `tags` (labels — v1.1). These are easy additions later.

### Q6: Query Interface and Pagination

**Current state**: Spec shows `query(filter: EventFilter) -> list[ActivityEvent]` with individual parameters.

**Recommended approach**: Query returns `list[ActivityEvent]` capped at `limit` (default 100, max 1000). No cursor/offset pagination in v1.

```python
@dataclass
class EventFilter:
    type: str | None = None
    source: str | None = None
    severity: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
```

- **Pros**: Simple implementation, covers all use cases for v1; limit prevents unbounded results; filter object is extensible
- **Cons**: No pagination means users can't iterate beyond 1000 events (acceptable for v1)
- **Effort**: Low

**Alternatives considered**: Cursor-based pagination with `last_id` parameter. Rejected for v1 — adds complexity without demonstrated need.

### Q7: Exception Strategy

**Current state**: `core/exceptions.py` has `StorageError("Raised when a storage operation fails")`.

**Recommended approach**: **Reuse `StorageError` for v1.**

```python
from apoch.core.exceptions import StorageError

# Usage in storage.py:
raise StorageError("Failed to write event to chronicle.db: ...")
```

- **Pros**: Consistent with existing error hierarchy; callers can catch `ApochError` or `StorageError` regardless of which module raises it; no new imports needed in the exception module
- **Cons**: Less granular error handling (can't distinguish Chronicle storage errors from future module storage errors)
- **Effort**: Trivial

**Alternatives considered**: Add `ChronicleStorageError(StorageError)` to `core/exceptions.py`. Rejected for v1 — can add later without breaking changes since it's a subclass.

### Q8: Test Location

**Current state**: 18 flat test files in `tests/`. No module-specific subdirectories.

**Recommended approach**: `tests/modules/chronicle/` — modular structure:

```
tests/modules/chronicle/
├── __init__.py
├── test_module.py    # Lifecycle: start, stop, shutdown, state transitions
└── test_storage.py   # SqliteEventStore: record, query, prune, stats, edge cases
```

- **Pros**: Scales cleanly as more modules are added; keeps module tests isolated; follows the same package structure as `src/apoch/modules/`
- **Cons**: Slightly longer import paths; must ensure `conftest.py` coverage (no issue — root `conftest.py` covers all)
- **Effort**: Low

**Alternatives considered**: Flat `tests/test_chronicle.py`. Rejected — as more modules appear (Guardian, Vision), flat test files become unwieldy and harder to navigate.

### Q9: StorageEngine ABC

**Current state**: No storage abstraction exists.

**Recommended approach**: **No ABC in v1.** Single `SqliteEventStore` class with well-defined public methods.

- **Pros**: YAGNI — zero overhead, zero abstraction cost, maximum simplicity; if a second backend is ever needed, extract the ABC then (the `SqliteEventStore` method signatures become the ABC interface)
- **Cons**: Slightly more work to swap backends later (mechanical extraction, not architectural)
- **Effort**: None required for v1

**Alternatives considered**: Define `EventStore(ABC)` with `record`, `query`, `prune`, `stats` as abstract methods. Rejected for v1 — premature abstraction.

### Q10: Config Flow for Chronicle

**Current state**: `Module.__init__(config: dict)` receives per-module config from `ModuleRegistry.load()`. The Engine config lives in `config["modules"]["chronicle"]`. `ConfigLoader` reads YAML from `~/.config/apoch/config.yaml`.

**Recommended approach**: Chronicle reads from `self._config` (the Module ABC's config dict). No direct ConfigLoader usage.

Example config YAML:
```yaml
modules:
  chronicle:
    enabled: true
    db_path: /custom/path/chronicle.db   # optional override
    retention_days: 30                   # optional override
```

- **Pros**: Consistent with all other modules; the Registry already injects the correct config slice; no circular dependency risk
- **Cons**: Config is a bare dict — no typing/validation (acceptable for v1, can use Pydantic later)
- **Effort**: Low

**Alternatives considered**: Chronicle reads ConfigLoader directly. Rejected — violates the core dependency rule (modules should not import config directly) and bypasses the per-module config injection that the Registry already provides.

## Recommendation

| # | Area | Recommendation | Effort |
|---|------|---------------|--------|
| 1 | Package structure | `src/apoch/modules/chronicle/{__init__,module,storage,models}.py` | Low |
| 2 | Module ABC integration | Extend `Module` directly, no extra state wrapping | Low |
| 3 | SQLite approach | Single `SqliteEventStore` class, stdlib `sqlite3`, WAL mode | Low |
| 4 | Data directory | Add `user_data_dir()` to `_compat.py` + Chronicle default resolves there | Low |
| 5 | Event schema | Frozen dataclass with UUID, timezone-aware datetime, payload as dict | Low |
| 6 | Query interface | `list[ActivityEvent]` with `limit` (default 100, max 1000), no v1 pagination | Low |
| 7 | Exceptions | Reuse `StorageError` from `core/exceptions.py` | Trivial |
| 8 | Test location | `tests/modules/chronicle/` — modular structure | Low |
| 9 | Storage ABC | No ABC in v1 — single class only | None |
| 10 | Config flow | Through `self._config` from Module ABC | Low |

**Overall recommendation**: Proceed with all recommendations above. The codebase foundation is solid and well-suited for the first concrete module.

## Risks

1. **SQLite write throughput**: The spec requires 10,000 events in under 10 seconds. WAL mode + batched inserts may be needed. Mitigation: implement WAL from day one; benchmark during development.
2. **Data directory cross-platform**: `XDG_DATA_HOME` is Linux/macOS convention. Windows needs `%APPDATA%`. Mitigation: `_compat.py` already handles platform detection — adding `user_data_dir()` there ensures correct behavior.
3. **DB migration in v1.1**: If the schema changes, there's no migration system. Mitigation: use a `schema_version` table from day one so future migrations are possible.
4. **Config dict is untyped**: `self._config` is a bare `dict`. Chronicle will do manual `.get("key", default)` lookups. Mitigation: acceptable for v1; document expected keys clearly.

## Ready for Proposal

**Yes** — proceed to `sdd-propose`. All 10 questions have clear recommendations grounded in the existing codebase patterns.
