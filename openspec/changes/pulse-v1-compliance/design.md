# Design: Pulse v1 Compliance

## Technical Approach

Three independent work units, each closing one specification gap. Changes are scoped to existing files only — no new modules, no new entry points, no new dependencies.

## Architecture Decisions

### R2 — Cost Attribution

| Decision | Option | Tradeoff | Choice |
|----------|--------|----------|--------|
| Where to compute | Module vs Storage vs PricingTable | SRP vs YAGNI | **Module** — `PulseModule.record()` calculates cost, consistent with Chronicle config pattern |
| Pricing config | Module config dict vs dedicated class | Simplicity vs extensibility | **Module config dict** (`config.get("model_pricing", {})`) — YAGNI for v1 |
| Missing price behaviour | Log + keep None vs raise error | Graceful vs strict | **Log warning + keep None** — spec says SHOULD report, not MUST fail |

### R5 — Rework Analysis

| Decision | Option | Tradeoff | Choice |
|----------|--------|----------|--------|
| Rework method detection | Auto-detect line data vs explicit flag | Magic vs explicit | **Auto-detect** — if any unit has `lines_original > 0`, use line-based; else token fallback |
| Window filtering | By completed_at vs created_at vs config | Accuracy vs availability | **completed_at** — spec says "modified within N days after initial implementation" uses completion time |
| Clamping | Clamp to [0, 1] vs report raw | Realistic vs transparent | **Clamp to 1.0** — >100% rework doesn't make physical sense |

### R10 — Cross-Session Persistence

| Decision | Option | Tradeoff | Choice |
|----------|--------|----------|--------|
| Backend | SQLite vs JSON vs filesystem-per-work-unit | Maturity vs simplicity | **SQLite** — proven Chronicle pattern, atomic writes, queryable |
| Cache strategy | SQLite-only vs write-through cache | Consistency vs speed | **SQLite-only** — no dual-write problems; in-memory dict for test isolation only |
| Schema versioning | Version table vs migration script | Future-proof vs YAGNI | **Version table** — Chronicle pattern, trivial to add, critical for future migrations |

## Data Flow (updated)

```
PulseModule.record(input):
  1. If input.cost is None and model has pricing:
     cost = pricing[model] × (input.tokens_input + input.tokens_output)
  2. If input.cost is None and model has NO pricing:
     log.warning("No price configured for model %s", model)
     cost stays None
  3. Delegate to PulseStore.save(input with computed cost)

Analysis.rework_rate(units, window_days=30):
  1. If units have lines_original > 0:
     filter by window_days
     rate = sum(lines_modified) / sum(lines_original)
     return clamp(rate, 0, 1)
  2. Else: fall back to token proxy

PulseModule.start():
  conn = sqlite3.connect(user_data_dir() / "pulse.db")
  store = PulseStore(conn)
  store.init_schema()

PulseModule.stop():
  conn.close()
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/pulse/models.py` | Modify | Add `lines_original`, `lines_modified` to `WorkUnit` and `MeasurementInput` |
| `src/apoch/modules/pulse/storage.py` | Modify | Add SQLite backend, `init_schema()`, dual-mode constructor |
| `src/apoch/modules/pulse/analysis.py` | Modify | Line-based rework, `window_days`, fallback, `rework_method` in summary |
| `src/apoch/modules/pulse/module.py` | Modify | Cost calculation in `record()`, pricing config, SQLite lifecycle, thread `window_days` |
| `tests/modules/pulse/test_models.py` | Modify | New field invariants |
| `tests/modules/pulse/test_analysis.py` | Modify | Line-based rework, window filtering, fallback |
| `tests/modules/pulse/test_storage.py` | Modify | SQLite persistence tests |
| `tests/modules/pulse/test_module.py` | Modify | Cost calculation, pricing config, persistence lifecycle |
| `pyproject.toml` | No change | — |
