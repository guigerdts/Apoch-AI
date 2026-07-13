# Design: PR3A — Chronicle Foundation

## Technical Approach

Single `ChronicleModule(Module)` with SQLite fully encapsulated behind `SqliteEventStore`. Three-layer split: `module.py` (lifecycle + public API), `storage.py` (all SQLite ops), `models.py` (data types). Core never touches the database. Spec: `module-chronicle`.

## Architecture Decisions

### Decision: Three-layer vs monolithic Module

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single file (all in module.py) | Less files, but SQL mixed with lifecycle; harder to test storage in isolation | ❌ |
| module.py + storage.py + models.py | Test storage with any DB path, mock storage in module tests | ✅ Clean separation per existing Core conventions |

### Decision: Connection ownership

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Module owns connection, passes to store | Store is stateless w.r.t. connection lifecycle; module controls DB open/close | ✅ Module owns `sqlite3.connect()`, injects into `SqliteEventStore` |
| Store opens its own connection | Store manages its own lifecycle but complicates cleanup ordering | ❌ |

### Decision: user_data_dir() location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Extend `_compat.py` with `user_data_dir()` | Follows XDG_DATA_HOME (`~/.local/share/apoch`) separate from `user_config_dir()` (XDG_CONFIG_HOME) | ✅ XDG convention; config and data are separate concerns |

### Decision: Payload serialization

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `json.dumps`/`loads` in TEXT column | Simple, portable, no deps; optional `"schema"` key survives round-trip | ✅ |
| Pydantic or pickle | Unnecessary for dict payloads; pickle is security risk | ❌ |

### Decision: Auto-prune timing

| Option | Tradeoff | Decision |
|--------|----------|----------|
| After table creation, before transitioning to RUNNING | Events are pruned before the module is usable; failures logged, never fatal | ✅ Silent & non-blocking per spec |
| Separate background task | Adds async complexity for v1 with no benefit | ❌ |

## Data Flow

```
 ChronicleModule.record(event)
       │  serialize → INSERT
       ▼
  SqliteEventStore  ──►  SQLite (WAL mode)
       │  SELECT ──► deserialize
       ▼
 ChronicleModule.query(filter)
       │
       ▼
   caller receives list[ActivityEvent]
```

```
 start():
   open DB ──► create tables ──► auto-prune ──► log completion ──► RUNNING

 stop():
   close DB conn ──► set conn = None ──► STOPPED
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/__init__.py` | Create | Package scaffold with `__all__` |
| `src/apoch/modules/chronicle/__init__.py` | Create | Sub-package init, exports |
| `src/apoch/modules/chronicle/models.py` | Create | `ActivityEvent`, `EventFilter`, `EventStats` dataclasses |
| `src/apoch/modules/chronicle/storage.py` | Create | `SqliteEventStore` — all SQLite operations |
| `src/apoch/modules/chronicle/module.py` | Create | `ChronicleModule(Module)` — lifecycle + public API |
| `src/apoch/_compat.py` | Modify | Add `user_data_dir()` following XDG_DATA_HOME |
| `pyproject.toml` | Modify | Register `chronicle = apoch.modules.chronicle.module:ChronicleModule` |
| `tests/modules/chronicle/test_storage.py` | Create | Storage tests with `tmp_path` isolation |
| `tests/modules/chronicle/test_module.py` | Create | Lifecycle tests + record→query→prune integration |

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class ActivityEvent:
    id: str          # uuid4.hex
    timestamp: str   # ISO 8601 with µs, UTC
    type: str        # e.g. "lifecycle", "tool_invocation", "error"
    source: str      # module name
    severity: str    # "info" | "warning" | "error" | "fatal"
    payload: dict    # free-form; optional "schema" key

@dataclass
class EventFilter:
    type: str | None = None
    source: str | None = None
    severity: str | None = None
    since: str | None = None    # ISO 8601
    until: str | None = None    # ISO 8601
    limit: int = 100

@dataclass
class EventStats:
    total: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
```

**SqliteEventStore** — accepts `sqlite3.Connection`, exposes `record()`, `query()`, `prune()`, `stats()` only. No DB path or lifecycle logic.

**ChronicleModule(Module)** — `start()` opens DB → creates store → runs auto-prune. `stop()` closes connection. `record`/`query`/`prune`/`stats` delegate to store. Config: `{"retention_days": 30}` (default 30).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit — storage | Record, query with all filters, prune, stats, WAL mode, schema_version table | `tmp_path` DB, direct `SqliteEventStore` calls |
| Unit — module | Lifecycle transitions (start→stop→shutdown), config passing, idempotent stop | Mock `SqliteEventStore`, assert state changes |
| Integration | Full record → query → prune cycle with real SQLite | `tmp_path`, `ChronicleModule.start()` → operate → `stop()`, verify data on new connection |
| Edge cases | Empty DB query, prune with no old events, WAL mode confirmed via `PRAGMA journal_mode` | Explicit assertions on PRAGMA results |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary in this change.

## Migration / Rollout

No migration required. First version — fresh DB created on first `start()`.

## Open Questions

None.
