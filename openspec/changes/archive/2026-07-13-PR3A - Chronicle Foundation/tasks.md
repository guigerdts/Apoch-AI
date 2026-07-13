# Tasks: PR3A — Chronicle Foundation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~400 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR (PR3A is already the first slice) |
| Delivery strategy | force-chained |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: _compat, scaffold, models | PR3A | `pytest tests/ -k "chronicle"` | N/A — unit tests only | `git revert` on changed files |
| 2 | Core: storage + module impl | PR3A | `pytest tests/ -k "chronicle"` | N/A — unit tests only | Revert pyproject.toml + rm `modules/chronicle/` |
| 3 | Tests: storage + module tests | PR3A | `pytest tests/modules/chronicle/ -v` | `tmp_path` isolation | Revert `tests/modules/chronicle/` |

## Phase 1: Foundation

- [x] 1.1 Add `user_data_dir()` to `src/apoch/_compat.py` — follows XDG_DATA_HOME (`~/.local/share/apoch`), same `$APOCH_HOME` override pattern as `user_config_dir()`
- [x] 1.2 Create `src/apoch/modules/__init__.py` — package scaffold with `__all__ = ["chronicle"]`
- [x] 1.3 Create `src/apoch/modules/chronicle/__init__.py` — sub-package init exporting `ChronicleModule`
- [x] 1.4 Create `src/apoch/modules/chronicle/models.py` — frozen `ActivityEvent` (id/uuid4, timestamp/ISO, type, source, severity, payload/dict w/ optional `schema`), `EventFilter` (type/source/severity/since/until/limit=100), `EventStats` (total, by_type, by_severity) dataclasses

## Phase 2: Core Implementation

- [x] 2.1 Register chronicle entry point in `pyproject.toml`: `chronicle = apoch.modules.chronicle.module:ChronicleModule` under `[project.entry-points."apoch.modules"]`
- [x] 2.2 Create `src/apoch/modules/chronicle/storage.py` — `SqliteEventStore(dict)` with:
  - `init_schema()`: CREATE `events` table (id TEXT PK, timestamp TEXT, type TEXT, source TEXT, severity TEXT, payload TEXT), CREATE `schema_version` table (version INT, applied_at TEXT); enable WAL via `PRAGMA journal_mode=WAL`
  - `record(event)`: serialize payload via json.dumps, INSERT
  - `query(filter)`: dynamic WHERE clauses for type/source/severity/since/until, ORDER BY timestamp DESC, LIMIT; deserialize payload via json.loads
  - `prune(before)`: DELETE events WHERE timestamp < before, return count
  - `stats()`: SELECT COUNT(\*), GROUP BY type, GROUP BY severity
  - Raises `StorageError` on DB failure, never raw sqlite3 exceptions
- [x] 2.3 Create `src/apoch/modules/chronicle/module.py` — `ChronicleModule(Module)`:
  - `__init__(config)`: accepts `{"retention_days": 30}` default
  - `start(context)`: resolve DB path via `user_data_dir() / "chronicle.db"`, open connection, init `SqliteEventStore`, run auto-prune (silent, non-blocking, catches exceptions), log completion
  - `stop()`: close connection, set conn = None
  - `shutdown()`: inherited (no-op after stop)
  - `record(event)`: delegate to store.record
  - `query(filter)`: delegate to store.query
  - `prune()`: delegate to store.prune with `retention_days`
  - `stats()`: delegate to store.stats

## Phase 3: Testing

- [x] 3.1 Create `tests/modules/chronicle/test_storage.py` — test schema init creates tables, WAL mode confirmed via PRAGMA, record and query round-trip preserves all fields, query with filters (type, source, severity, time range, limit) returns correct subset, query with no matches returns empty list, prune removes old events only, prune with no old events is no-op, stats returns accurate counts, `StorageError` raised on corrupt DB
- [x] 3.2 Create `tests/modules/chronicle/test_module.py` — test lifecycle: LOADED after init, RUNNING after start(), STOPPED after stop(), SHUTDOWN after shutdown(); config dict passes retention_days to store; auto-prune runs during start (verify via store mock); record→query→prune integration with real `tmp_path` SQLite; idempotent stop (safe to call twice)
