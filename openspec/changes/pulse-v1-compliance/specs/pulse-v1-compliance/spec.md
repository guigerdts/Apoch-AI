# Specification: Pulse v1 Compliance

This change closes three specification gaps identified in the pulse-productivity-intelligence audit. The requirements below are **additions or corrections** to the existing Pulse spec — they supersede the corresponding implementation behaviour but do not replace the original requirement text.

## R2 — Cost Attribution (Configurable Pricing)

### Requirement

Pulse MUST attribute monetary cost to each measured work unit using configurable model pricing.

### Changes to existing implementation

- `PulseModule` MUST accept a `model_pricing` config dict: `{model_name: price_per_token}`
- `PulseModule.record()` MUST calculate `cost = pricing[model] × (tokens_input + tokens_output)` when `MeasurementInput.cost is None`
- When `MeasurementInput.cost` is provided, it MUST be used as-is (external override)
- When a model has no configured price, a warning MUST be logged AND `cost` MUST remain `None`

### Acceptance Criteria

1. GIVEN a `PulseModule` with `model_pricing = {"claude-4": Decimal("0.00001")}` WHEN a measurement is recorded without cost THEN the cost SHALL be `(tokens_input + tokens_output) × 0.00001`
2. GIVEN a `PulseModule` with pricing config WHEN a measurement is recorded WITH an explicit cost THEN the provided cost SHALL be used (not recalculated)
3. GIVEN a `PulseModule` WITHOUT pricing for the recorded model WHEN a measurement is recorded without cost THEN cost SHALL remain `None` AND a warning SHALL be logged

## R5 — Rework Analysis (Line-Based)

### Requirement

Pulse MUST calculate rework percentage as `(modified lines ÷ original lines) × 100` using evidence (diff/metadata), with a configurable time window.

### Changes to existing implementation

- `WorkUnit` and `MeasurementInput` MUST add `lines_original: int = 0` and `lines_modified: int = 0`
- `Analysis.rework_rate(units, window_days=30)` MUST:
  - Use line-based calculation when any unit has `lines_original > 0`
  - Filter units outside the `window_days` window (based on `completed_at` from earliest `created_at`)
  - Calculate: `round(min(sum(lines_modified) / sum(lines_original), 1.0), 4)`
  - Fall back to token proxy when no unit has line data
- `ProductivitySummary` MUST include a `rework_method: str` field: `"line"`, `"token"`, or `"none"`

### Acceptance Criteria

1. GIVEN units with `lines_original=100, lines_modified=20` WHEN rework_rate is called THEN the result SHALL be 0.2
2. GIVEN units where `lines_modified > lines_original` WHEN rework_rate is called THEN the result SHALL be clamped to 1.0
3. GIVEN units with no line data WHEN rework_rate is called THEN the token proxy SHALL be used AND `rework_method` SHALL be `"token"`
4. GIVEN units with mixed line/token data WHEN rework_rate is called THEN line-based SHALL be used (token is fallback only)
5. GIVEN an empty list WHEN rework_rate is called THEN 0.0 SHALL be returned AND `rework_method` SHALL be `"none"`

## R10 — Cross-Session Persistence

### Requirement

Pulse MUST preserve all measurements across session boundaries and deployment restarts.

### Changes to existing implementation

- `PulseStore` MUST accept an optional `sqlite3.Connection` parameter
- When a connection is provided, all operations SHALL use SQLite as the backing store
- When no connection is provided, the in-memory dict SHALL be used (backward compatibility for tests)
- `PulseStore.init_schema()` MUST create a `work_units` table with `schema_version` tracking
- `PulseModule.start()` MUST open a SQLite connection at `user_data_dir() / "pulse.db"` and pass it to `PulseStore`
- `PulseModule.stop()` MUST close the SQLite connection
- All SQLite errors MUST be wrapped in `StorageError`

### Acceptance Criteria

1. GIVEN a SQLite-backed PulseStore WHEN a measurement is saved AND the store is re-opened THEN the measurement SHALL be retrievable
2. GIVEN a SQLite-backed PulseStore WHEN `list()` is called THEN it SHALL return all stored measurements
3. GIVEN a SQLite-backed PulseStore WHEN `count()` is called THEN it SHALL return the correct count
4. GIVEN a SQLite-backed PulseStore WHEN a duplicate ID is saved THEN `StorageError` SHALL be raised
5. GIVEN a SQLite-backed PulseStore WHEN the connection is closed AND an operation is attempted THEN `StorageError` SHALL be raised
