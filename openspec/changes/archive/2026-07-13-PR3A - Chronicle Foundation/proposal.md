# Proposal: PR3A - Chronicle Foundation

## Intent

Create Apoch-AI's first concrete module — the Chronicle — providing persistent activity recording, retention, and querying for lifecycle events, tool invocations, errors, and user actions.

## Scope

### In Scope
- `apoch/modules/` package scaffold with `chronicle/` sub-package
- `ChronicleModule(Module)` with lifecycle (`start`/`stop`/`shutdown`)
- SQLite storage engine (WAL mode, `schema_version` table, microsecond precision)
- `ActivityEvent` frozen dataclass (id, timestamp, type, source, severity, payload with optional `schema` field)
- `record(event)`, `query(filter)`, `prune(before)`, `stats()` public API
- Auto-prune at startup (silent, idempotent, non-blocking)
- 30-day default retention, configurable via module config dict
- Entry point: `chronicle = apoch.modules.chronicle.module:ChronicleModule`
- `user_data_dir()` helper in `_compat.py`

### Out of Scope
- MCP tool registration (deferred to PR3B)
- Guardian / Vision module integration
- Cursor/offset pagination (deferred)
- Size-based pruning (deferred)
- DB migration runner (`schema_version` table only — no runner)
- Event streaming or external log shipping

## Capabilities

### New Capabilities
None — `module-chronicle` spec already exists and is implemented as defined.

### Modified Capabilities
None — no spec-level changes; pure implementation.

## Approach

Single `ChronicleModule(Module)` in `module.py` owning lifecycle and public API. `SqliteEventStore` in `storage.py` encapsulating all SQLite operations. `ActivityEvent`, `EventFilter`, `EventStats` in `models.py`. Core never touches the database. DB path resolves via `user_data_dir()` from `_compat.py` — `~/.local/share/apoch/chronicle.db` on Linux. WAL mode enabled at connection init. `schema_version` table created but no migration runner in v1.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/apoch/modules/` | New | Package scaffold for first-party modules |
| `src/apoch/modules/__init__.py` | New | Package init with `__all__` exports |
| `src/apoch/modules/chronicle/` | New | Sub-package (module, storage, models) |
| `src/apoch/_compat.py` | Modified | Add `user_data_dir()` following XDG convention |
| `pyproject.toml` | Modified | Register `chronicle` entry point under `apoch.modules` |
| `tests/modules/chronicle/` | New | Lifecycle tests + storage tests with `tmp_path` isolation |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SQLite write contention under high throughput | Low | WAL mode from day one; batch writes if needed in v1.1 |
| DB file location differs by OS | Low | `_compat.py` handles Linux/macOS/Windows explicitly |
| Unbounded DB growth before prune | Low | Auto-prune at startup; 30-day default retention limits accumulation |

## Rollback Plan

Remove `chronicle` entry from `pyproject.toml`, delete `src/apoch/modules/chronicle/`, revert `user_data_dir()` addition in `_compat.py`, delete `tests/modules/chronicle/`.

## Dependencies

- `Module(ABC)` from `apoch.core.module` — stable, no changes needed
- `StorageError` from `apoch.core.exceptions` — exists, reused
- `Context` from `apoch.core.module` — passed to `start()`
- Python stdlib: `sqlite3`, `uuid`, `datetime`, `pathlib`

## Success Criteria

- [ ] Chronicle loads, starts, stops, and shuts down per Module ABC lifecycle
- [ ] `record()` persists events durably (survives process restart)
- [ ] `query()` returns correct filtered subsets with limit capping
- [ ] `prune()` removes events older than retention, preserves newer ones
- [ ] Auto-prune runs silently at startup, never blocks boot
- [ ] All SQLite operations use WAL mode
- [ ] `schema_version` table exists after DB initialization
- [ ] Test suite passes with `tmp_path` isolation (no side effects)
