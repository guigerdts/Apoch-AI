# Tasks: Optimizer — Engineering Optimization Intelligence

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600-850 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (models + confidence + detectors) → PR 2 (module + lifecycle) → PR 3 (wiring + registration) → PR 4 (integration tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Domain models + confidence helpers | PR 1 | `uv run pytest tests/modules/optimizer/test_models.py -v` | N/A — dataclass-only, no runtime deps | Revert `src/apoch/modules/optimizer/models.py` + `src/apoch/modules/optimizer/_confidence.py` |
| 2 | All 6 detectors with full test coverage | PR 1 | `uv run pytest tests/modules/optimizer/test_detectors.py -v` | `WorkUnit(...)` fixture construction | Revert `src/apoch/modules/optimizer/_detectors.py` + `tests/modules/optimizer/test_detectors.py` |
| 3 | OptimizerModule lifecycle + orchestration | PR 2 | `uv run pytest tests/modules/optimizer/test_module.py -v -k "TestLifecycle or TestOrchestration"` | Construct `OptimizerModule(config)`, call `start(context)` | Revert `src/apoch/modules/optimizer/module.py` + `tests/modules/optimizer/test_module.py` |
| 4 | Service wiring, __init__, registration | PR 3 | `uv run pytest tests/modules/optimizer/test_module.py -v -k "TestServices or TestRegistration"` | `from apoch.modules.optimizer import OptimizerModule` + verify entry point | Revert `src/apoch/modules/optimizer/__init__.py`, `src/apoch/modules/__init__.py`, `pyproject.toml` changes |
| 5 | Integration + end-to-end + boundary tests | PR 4 | `uv run pytest tests/modules/optimizer/ -v` | Full Pulse → Optimizer pipeline or standalone mode | Entire PR boundary — reversions across all files |

---

## Phase 1: Domain Models & Confidence Helpers

- [x] 1.1 **RED**: Write `tests/modules/optimizer/test_models.py` — `OptimizationHypothesis` construction, field types, frozen immutability, default values. Verify it fails (module doesn't exist yet).
- [x] 1.2 **GREEN**: Create `src/apoch/modules/optimizer/models.py` — `@dataclass(frozen=True)` with `type: Literal[...]`, `domain: Literal[...]`, `confidence: float`, `evidence: dict`, `affected_scope: str`, `generated_at: str`. Expose via `__all__`. Verify tests pass.
- [x] 1.3 **RED+GREEN**: Create `src/apoch/modules/optimizer/_confidence.py` — `cap_underpowered(score, n)` helper. Test boundary values: n<3 → cap at 0.5, n≥3 → score unchanged, 0.0 and 1.0 clamping, determinism.

## Phase 2: Detector Protocol & Baseline Generator

- [x] 2.1 **RED**: Write `tests/modules/optimizer/test_detectors.py` — `TestBaselineGenerator`: happy path (3+ units), empty list, partial data (None costs), determinism (same input × 2 → bitwise identical), Pulse unavailable (empty).
- [x] 2.2 **GREEN**: Implement `Detector` protocol + `BaselineGenerator` in `src/apoch/modules/optimizer/_detectors.py`. `detect()` returns `list[OptimizationHypothesis]` with mean/std/min/max for tokens_input, tokens_output, cost, wall_clock_s. Verify tests pass.

## Phase 3: Remaining Five Detectors

- [x] 3.1 **RED**: `DegradationDetector` tests — degradation detected (z-score exceed), no baseline, incomplete data, determinism, pulse unavailable.
- [x] 3.2 **GREEN**: Implement `DegradationDetector` — z-score vs baseline, sigmoid-mapped confidence, `<3 data points → cap 0.4`.
- [x] 3.3 **RED**: `ModelEfficiencyDetector` tests — multiple models compared, single model (no hypothesis), partial cost data with evidence note, determinism.
- [x] 3.4 **GREEN**: Implement `ModelEfficiencyDetector` — cost-per-token and time-per-unit per model, effect_size / max_effect confidence, single model → empty.
- [x] 3.5 **RED**: `AnomalyDetector` tests — outlier detected (IQR method), no outliers, incomplete distribution (<3 points → no hypothesis), determinism.
- [x] 3.6 **GREEN**: Implement `AnomalyDetector` — IQR-based outlier detection on cost/time, `1 - (distance / max_distance)` confidence.
- [x] 3.7 **RED**: `SessionPatternDetector` tests — temporal pattern detected (time clustering), insufficient data (<3 units), missing timestamps excluded, determinism.
- [x] 3.8 **GREEN**: Implement `SessionPatternDetector` — time-of-day clustering via hour histogram, `cluster_size / total` confidence, `<3 units → empty`.
- [x] 3.9 **RED**: `ReworkCorrelationDetector` tests — correlation detected (model→rework, duration→rework), no rework data, partial condition fields noted in evidence, determinism.
- [x] 3.10 **GREEN**: Implement `ReworkCorrelationDetector` — correlate rework metrics with conditions, `abs(correlation_coeff)` confidence, no rework → empty.

## Phase 4: OptimizerModule — Lifecycle + Orchestration

- [ ] 4.1 **RED**: Write `tests/modules/optimizer/test_module.py` — `TestLifecycle`: initial LOADED state, start→RUNNING, stop→STOPPED, shutdown→SHUTDOWN, full lifecycle, idempotent stop via `_pre_stop` guard.
- [ ] 4.2 **GREEN**: Create `src/apoch/modules/optimizer/module.py` — `OptimizerModule(Module)` with `start()` (register 6 detectors, store context), `stop()` (clear state), `shutdown()` (no-op), sentinel `_get_measurements()`. Verify lifecycle tests pass.
- [ ] 4.3 **RED**: `TestOrchestration` — `_run_cycle()` returns flat hypotheses, detector isolation (one detector raises → others still produce results), stable sort order (detector order → confidence desc → generated_at asc), determinism (same input × 2 → identical list).
- [ ] 4.4 **GREEN**: Wire `_run_cycle()` with `try/except` per detector, `_sort_hypotheses()` for stable ordering. Verify orchestration tests pass.

## Phase 5: Services, Registration, Entry Points

- [ ] 5.1 **RED+GREEN**: Add `services` property: `"optimizer.hypotheses"` → `_run_cycle`, `"optimizer.baselines"` → `_get_baselines`, `"optimizer.status"` → `_get_status`. Test service wiring, correct types, Pulse optionality (`pulse_connected: false`), status dict shape.
- [ ] 5.2 **RED+GREEN**: Create `src/apoch/modules/optimizer/__init__.py` — lazy-import `OptimizerModule` via `__getattr__` (Pulse pattern). Test import, `__all__`.
- [ ] 5.3 **RED+GREEN**: Modify `src/apoch/modules/__init__.py` — add `"optimizer"` to `__all__`. Modify `pyproject.toml` — add `optimizer = "apoch.modules.optimizer.module:OptimizerModule"` entry point. Test entry point resolution via `importlib.metadata.entry_points`.

## Phase 6: Integration & End-to-End Validation

- [ ] 6.1 **RED+GREEN**: Full integration test: create `Context` with Pulse `pulse.measurements` → start `OptimizerModule` → run cycle → verify hypotheses of correct types with confidence in [0.0, 1.0].
- [ ] 6.2 **RED+GREEN**: Pulse absent test: start without Pulse → empty hypotheses, `pulse_connected: false`, `hypothesis_count: 0`.
- [ ] 6.3 **RED+GREEN**: Purity tests: input list not mutated after `_run_cycle()`, frozen dataclass enforced at field-write.
- [ ] 6.4 **RED+GREEN**: Boundary tests: single WorkUnit (underpowered → capped confidence), empty list, thousands of units, all-None metrics.
- [ ] 6.5 **RED+GREEN**: Determinism test: same input × 2 calls → `==` on full hypothesis list (excluding `generated_at`), identical output shape.

## Phase 7: Cleanup

- [ ] 7.1 Run full test suite: `uv run pytest tests/modules/optimizer/ -v`. All RED+GREEN pairs pass, no stray files.
- [ ] 7.2 `uv run ruff check src/apoch/modules/optimizer/ tests/modules/optimizer/` — no lint violations.
