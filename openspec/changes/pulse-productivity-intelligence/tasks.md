# Tasks: Pulse — Engineering Productivity Intelligence

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

> Pulse es un módulo nuevo (~370 líneas estimadas). Un solo PR de tamaño normal.

## Compliance Status

**Specification compliance: 8/11** — R1–R11 audit result:
- R1 ✅ Token Measurement
- R2 ❌ Cost Attribution (external, not calculated — deferred to pulse-v1-compliance)
- R3 ✅ Time Measurement
- R4 ✅ Model Attribution
- R5 ❌ Rework Analysis (token proxy, not line-based — deferred to pulse-v1-compliance)
- R6 ✅ Trend Data
- R7 ✅ Optimizer Integration
- R8 ✅ Oracle Integration
- R9 ✅ Data Privacy
- R10 ❌ Cross-Session Persistence (in-memory only — deferred to pulse-v1-compliance)
- R11 ✅ Measurement Independence

**Release: Beta / Preview** — functional v1 with documented gaps.

## Phase 1: Domain Models

- [x] 1.1 Create `src/apoch/modules/pulse/models.py` — `MeasurementInput`, `WorkUnit`, `TrendPoint` dataclasses. Tests: append-only invariants, field validation, privacy constraints (no content/identity fields).

## Phase 2: Persistence

- [x] 2.1 Create `src/apoch/modules/pulse/storage.py` — `PulseStore` (single class, append-only). Tests: write → read back → range queries → append-only enforcement.

## Phase 3: Module Lifecycle

- [x] 3.1 Create `src/apoch/modules/pulse/module.py` — `PulseModule(Module)` with lifecycle start/stop/shutdown + measurement ingestion wiring. Create `src/apoch/modules/pulse/__init__.py`. Tests: Module ABC lifecycle, accept and store measurement end-to-end.

## Phase 4: Analysis

- [x] 4.1 Add rework calculation and trend derivation methods to `PulseModule`. Tests: deterministic rework % from known input, trend shape from 2+ work units, edge cases (single work unit, no rework).

## Phase 5: System Integration

- [x] 5.1 Add cross-module `@property services` (duck-typed, key `"pulse.measurements"`). Add pulse entry point in `pyproject.toml` + `"pulse"` to `src/apoch/modules/__init__.py`. Tests: service discovery, entry point resolution.
