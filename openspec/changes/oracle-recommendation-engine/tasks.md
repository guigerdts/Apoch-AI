# Tasks: Oracle — Recommendation Engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~650 (range 550–750) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Models + Engine) → PR 2 (Module + Wiring) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Domain models + pure RecommendationEngine with tests | PR 1 | `pytest tests/apoch/modules/oracle/test_models.py tests/apoch/modules/oracle/test_engine.py -v` | N/A — pure functions, no I/O | Delete `src/apoch/modules/oracle/models.py`, `engine.py`, test files |
| 2 | OracleModule lifecycle/adapters + wiring + integration tests | PR 2 | `pytest tests/apoch/modules/oracle/test_module.py -v` | `pytest tests/apoch/modules/oracle/ -v` (full oracle suite) | Remove entry point from `pyproject.toml`, delete `oracle/` package |

## Phase 1: Domain Models

### Task 1.1: `Recommendation` frozen dataclass + status/priority types

**Files**: `src/apoch/modules/oracle/models.py`, `tests/apoch/modules/oracle/test_models.py`
**Requirement**: R4, R9, R11
**Description**: Create `Recommendation` frozen dataclass with all 13 fields (`id`, `title`, `description`, `priority`, `confidence`, `evidence`, `justification`, `dependencies`, `expiration`, `source_hypotheses`, `domain`, `status`, `created_at`). Create `RecommendationStatus` StrEnum (`active`/`accepted`/`rejected`/`expired`), domain Literal type (`cost`/`time`/`rework`/`model_efficiency`/`session_behavior`/`general`), priority Literal type (`critical`/`high`/`medium`/`low`).
**Acceptance**: Frozen dataclass raises `FrozenInstanceError` on write. All field types match the spec output contract. Status enum has exactly 4 values.
**Test (RED first)**: `test_models.py` — construction with valid fields, immutability assertion, field type validation, status enum string values match spec.

## Phase 2: RecommendationEngine

### Task 2.1: `RecommendationEngine.generate()` — hypothesis-to-recommendation mapping

**Files**: `src/apoch/modules/oracle/engine.py`, `tests/apoch/modules/oracle/test_engine.py`
**Requirement**: R1, R3, R10, Constraint A
**Description**: Pure `RecommendationEngine` with `generate(hypotheses, health=None) -> list[Recommendation]`. Maps each `OptimizationHypothesis` to a `Recommendation` using the priority mapping table (domain × hypothesis type → priority + confidence). Each recommendation gets a UUID `id`, ISO 8601 `created_at`, `source_hypotheses` populated from input IDs, and `evidence` from hypothesis evidence. Empty input → empty list. Incomplete hypotheses → valid recs with degraded confidence. No I/O, no service discovery, no state mutation.
**Acceptance**: Every input hypothesis produces a valid `Recommendation`. Empty input returns `[]` without error. Partial input still produces valid recs. Deterministic: same input → same output across calls.
**Test (RED first)**: `test_engine.py` — happy path with full hypotheses, empty list, partial/missing fields, determinism (same input × 2 → identical output).

### Task 2.2: Deterministic prioritization and sorting

**Files**: `src/apoch/modules/oracle/engine.py`, `tests/apoch/modules/oracle/test_engine.py`
**Requirement**: R2, R10
**Description**: Sort output by tiebreaker chain: `priority` (critical > high > medium > low) → `confidence` descending → `created_at` ascending → `id` lexicographic. Apply priority bonus (one tier up) when confidence ≥ 0.9 AND domain is cost/time/rework.
**Acceptance**: Critical always sorts before high, high before medium, etc. Within same priority, higher confidence sorts first. Tied priority + confidence → deterministic by created_at then id.
**Test (RED first)**: Mixed priority sorting, confidence tiebreaker, triple-tied recs (same priority + confidence → deterministic by created_at → id), confidence threshold bonus.

### Task 2.3: Expiration logic

**Files**: `src/apoch/modules/oracle/engine.py`, `tests/apoch/modules/oracle/test_engine.py`
**Requirement**: R4
**Description**: On-read expiration check: compare `created_at + domain_TTL` against current time. Default TTLs: critical=1h, high=4h, medium=8h, low=24h. Configurable via engine constructor. Expired recs get `status: "expired"`.
**Acceptance**: Recs within TTL stay `active`. Recs past TTL become `expired`. Custom TTL config overrides defaults.
**Test (RED first)**: Fixed-clock test: rec exactly at TTL boundary, rec past TTL, rec within TTL, custom TTL config.

### Task 2.4: Health-based confidence degradation

**Files**: `src/apoch/modules/oracle/engine.py`, `tests/apoch/modules/oracle/test_engine.py`
**Requirement**: R7
**Description**: Optional `health: dict | None` parameter degrades confidence proportionally when Guardian diagnostics report module failures. `evidence` notes degradation source. Health absent → confidence used as-is.
**Acceptance**: Healthy modules → no degradation. Absent health dict → no degradation, no error. Failing module → confidence lowered, evidence captures source.
**Test (RED first)**: Full health (no degradation), no health dict, one module failing, multiple modules failing, all modules failing.

## Phase 3: OracleModule

### Task 3.1: Module ABC lifecycle

**Files**: `src/apoch/modules/oracle/module.py`, `tests/apoch/modules/oracle/test_module.py`
**Requirement**: R8, R9
**Description**: `OracleModule(Module)` with `start()`, `stop()`, `shutdown()`. `start()` stores context and instantiates `RecommendationEngine`. Follows same ABC pattern as OptimizerModule (`_pre_stop` idempotency, lifecycle state transitions).
**Acceptance**: Module transitions LOADED → RUNNING → STOPPED → SHUTDOWN. `start()` with no Optimizer → module does not crash. `stop()` is idempotent.
**Test (RED first)**: `test_module.py` — lifecycle state transitions, double start raises error, double stop is safe, shutdown from wrong state raises error.

### Task 3.2: Service wiring — `oracle.recommendations`

**Files**: `src/apoch/modules/oracle/module.py`, `tests/apoch/modules/oracle/test_module.py`
**Requirement**: R1, R6, R8, Constraint B
**Description**: `services` property returns `{"oracle.recommendations": self._get_recommendations}`. `_get_recommendations()` discovers `optimizer.hypotheses` via `context.services.get()` sentinel pattern (absent → `[]`), builds optional health context from Guardian/Vision, calls `self._engine.generate(hyps, health)`, writes Chronicle events via `_try_record`, returns sorted recs. OracleModule contains NO mapping rules or domain logic.
**Acceptance**: Optimizer present → generates recs. Optimizer absent → returns `[]`. Guardian absent → no degradation. All service lookups use sentinel, never crash.
**Test (RED first)**: Mock `context.services` with Optimizer present/absent, Guardian present/absent, verify `_get_recommendations` delegates to engine and returns correct output.

### Task 3.3: Chronicle event writing

**Files**: `src/apoch/modules/oracle/module.py`, `tests/apoch/modules/oracle/test_module.py`
**Requirement**: R5, R9
**Description**: `_try_record(recs)` writes `recommendation_generated` events via `chronicle.record` in a non-blocking try/except. Chronicle absent → skip silently. Partial Chronicle failures → log + continue. No Chronicle → ephemeral mode (recs still returned).
**Acceptance**: Chronicle available → events written with full `Recommendation` payload. Chronicle absent/partial failure → no crash, recs still returned.
**Test (RED first)**: Mock `chronicle.record` — verify event payload shape. Chronicle absent → no write attempted. Chronicle raises → logged and swallowed, recs still returned.

## Phase 4: Integration + Wiring

### Task 4.1: Package `__init__.py` with lazy import

**Files**: `src/apoch/modules/oracle/__init__.py`
**Requirement**: R11
**Description**: Create module package init with `__getattr__` lazy import pattern (same as `optimizer/__init__.py`). Exports `OracleModule`.
**Acceptance**: `from apoch.modules.oracle import OracleModule` works. `OracleModule` not loaded at import time — only when attribute accessed.

### Task 4.2: Module registration — `modules/__init__.py` + `pyproject.toml`

**Files**: `src/apoch/modules/__init__.py`, `pyproject.toml`
**Requirement**: R11
**Description**: Add `"oracle"` to `modules/__init__.py` `__all__`. Add entry point: `oracle = "apoch.modules.oracle.module:OracleModule"` under `[project.entry-points."apoch.modules"]` in `pyproject.toml`.
**Acceptance**: `apoch.modules.__all__` includes `"oracle"`. Entry point resolves: `importlib.metadata.entry_points(group="apoch.modules", name="oracle")` returns `OracleModule`.

### Task 4.3: End-to-end integration test

**Files**: `tests/apoch/modules/oracle/test_module.py`
**Requirement**: R1, R5, R6, R8
**Description**: Integration test with mocked `context.services` for Optimizer, Chronicle, Guardian. Full cycle: mock hypothesis input → `oracle.recommendations()` → sorted recs with correct priority/confidence → Chronicle events written.
**Acceptance**: Full cycle produces correct output. Removing any service degrades gracefully. Determinism across calls.
