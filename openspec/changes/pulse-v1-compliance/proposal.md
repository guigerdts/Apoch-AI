# Proposal: Pulse v1 Compliance — Close Specification Gaps

## Intent

Close three specification gaps identified during Pulse v1 architecture verification (8/11 compliance). Each gap represents a requirement (R2, R5, R10) that the implementation does not fully satisfy per the approved specification.

## Scope

### R2 — Cost Attribution (Configurable Pricing)

Implement configurable model pricing so cost is calculated as `token count × price per token` when not externally provided.

**In scope:**
- Module-config pricing dictionary (`dict[str, Decimal]` mapping model names to price-per-token)
- Cost calculation in `PulseModule.record()`: if `input.cost is None`, compute from pricing config
- Warning log when model has no configured price
- Tests for calculation, missing price, mixed scenarios

**Out of scope:**
- Dynamic pricing reload
- Persistent pricing store
- External pricing API

### R5 — Rework Analysis (Line-Based)

Replace token proxy with spec-compliant line-based rework calculation, keeping token proxy as fallback.

**In scope:**
- `lines_original: int` and `lines_modified: int` fields on `WorkUnit` and `MeasurementInput`
- `Analysis.rework_rate(units, window_days=30)` — line-based primary: `(sum(modified) / sum(original)) × 100`, clamped to [0, 100]
- Token proxy fallback when no line data exists
- `window_days` filtering: only units within the rework window contribute
- Tests for line-based, fallback, window filtering, edge cases

**Out of scope:**
- Automated diff parsing
- Git integration for line attribution
- Per-work-unit rework attribution (spec R5 says attributable to original work unit — deferred)

### R10 — Cross-Session Persistence (SQLite)

Replace in-memory PulseStore with SQLite-backed persistence following Chronicle's proven pattern.

**In scope:**
- `PulseStore.__init__(conn: sqlite3.Connection | None = None)` — SQLite when conn provided, in-memory dict fallback for tests
- `init_schema()` creating `work_units` table with schema version
- All CRUD operations migrated to SQLite (save, get, list, count)
- `PulseModule.start()` opens `user_data_dir() / "pulse.db"`, `stop()` closes it
- WAL mode for performance
- StorageError wrapping for all SQLite errors
- Tests via `tmp_path` (Chronicle pattern)

**Out of scope:**
- Multi-process safety
- Migration framework (new module, no existing data)
- Write-through cache

### NFRs

- Ruff clean
- 100% test pass rate (existing + new)
- No regressions in existing 427 tests
- No new entry points or module dependencies
- Deterministic: same inputs → same outputs (R5)

### Non-Goals

- No changes to R1, R3, R4, R6, R7, R8, R9, R11
- No new module features beyond closing the three gaps
- No API changes beyond what the gaps require
- No changes to the existing spec (spec is the contract)
