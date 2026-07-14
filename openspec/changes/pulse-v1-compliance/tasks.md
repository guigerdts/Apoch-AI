# Tasks: Pulse v1 Compliance

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
400-line budget risk: Low (scoped, no new modules)

> Tres gaps independientes en archivos existentes. ~200 líneas estimadas.

## Work Unit 1: R2 — Cost Attribution

- [ ] 1.1 Add `model_pricing` config to `PulseModule.__init__()`
- [ ] 1.2 Update `PulseModule.record()`: calculate cost when `input.cost is None` and model has pricing
- [ ] 1.3 Log warning when model has no configured price
- [ ] 1.4 Tests: calculation, explicit cost passthrough, missing price warning, edge cases

## Work Unit 2: R5 — Line-Based Rework

- [ ] 2.1 Add `lines_original`, `lines_modified` fields to `WorkUnit` and `MeasurementInput`
- [ ] 2.2 Update `Analysis.rework_rate()`: line-based primary, `window_days` parameter, token fallback
- [ ] 2.3 Add `rework_method` field to `ProductivitySummary`
- [ ] 2.4 Update `PulseModule.rework_rate()` to accept and pass `window_days`
- [ ] 2.5 Tests: line-based, clamping, window filtering, fallback, edge cases

## Work Unit 3: R10 — Cross-Session Persistence

- [ ] 3.1 Add optional `sqlite3.Connection` parameter to `PulseStore.__init__()`
- [ ] 3.2 Implement `PulseStore.init_schema()` — `work_units` table + `schema_version`
- [ ] 3.3 Implement SQLite-backed `save()`, `get()`, `list()`, `count()`
- [ ] 3.4 Update `PulseModule.start()`: open SQLite at `user_data_dir() / "pulse.db"`
- [ ] 3.5 Update `PulseModule.stop()`: close SQLite connection
- [ ] 3.6 Tests: SQLite persistence, lifecycle, error wrapping, edge cases
