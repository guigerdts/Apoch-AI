# Design: Optimizer — Engineering Optimization Intelligence

## Technical Approach

Optimizer follows the Module ABC lifecycle pattern (same as Pulse). Internally, six pure-function detectors share a common protocol and are orchestrated by `OptimizerModule`, which collects their output into a flat list of `OptimizationHypothesis` objects. Pulse data is consumed via duck-typed `context.services.get("pulse.measurements")` — absent Pulse means empty hypotheses, never an error.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| Detector interface | `Protocol` vs abstract base vs standalone functions | Protocol enforces shape without inheritance tax | `typing.Protocol` — detectors are stateless; no shared state to inherit |
| Hypothesis model | `dataclass(frozen=True)` vs `TypedDict` | Immutability guarantees purity vs lighter weight | `dataclass(frozen=True)` — matches `WorkUnit` pattern, language-enforced purity |
| Orchestration | Single run() call vs lazy/polling | Simplicity vs flexibility | Single `_run_cycle()` — all detectors evaluated on every call, no scheduler |
| Confidence scoring | Detector-level vs centralized | Per-detector nuance vs uniform rules | Per-detector `_confidence()` method with a shared `_cap_underpowered()` utility — each detector knows its own evidence semantics |
| Pulse optionality | `try/except KeyError` vs `context.services.get()` + sentinel | Sentinel is explicit, quieter | Sentinel pattern — `_get_measurements()` returns empty list when key is absent |

## Data Flow

```
context.services.get("pulse.measurements")
              │
              ▼
    _get_measurements() → list[WorkUnit] | []
              │
              ▼
      OptimizerModule._run_cycle()
              │
     ┌────────┼────────┬────────┬────────┬────────┐
     ▼        ▼        ▼        ▼        ▼        ▼
   Baseline Degrad.  ModelEff Anomaly  Session  Rework
   Generator Detector Detector Detector Pattern  Correl.
     │        │        │        │        │        │
     └────────┴────────┴────────┴────────┴────────┘
              │
              ▼
    list[OptimizationHypothesis]
```

## Module Structure

```
src/apoch/modules/optimizer/
├── __init__.py          # Exports OptimizerModule
├── models.py            # OptimizationHypothesis dataclass
├── module.py            # OptimizerModule — lifecycle + orchestration
├── _detectors.py        # Detector protocol + all 6 detector implementations
└── _confidence.py       # Shared confidence helpers (cap_underpowered, etc.)
```

## Data Model

```python
@dataclass(frozen=True)
class OptimizationHypothesis:
    type: Literal["pattern", "anomaly", "opportunity"]
    domain: Literal["cost", "time", "rework", "model_efficiency", "session_behavior"]
    confidence: float          # 0.0–1.0
    evidence: dict             # Detector-specific supporting data
    affected_scope: str        # Human-readable scope description
    generated_at: str          # ISO 8601, set at hypothesis creation
```

## Detector Protocol

```python
class Detector(Protocol):
    """Protocol every internal detector must satisfy."""

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Analyze WorkUnits and return hypotheses. Pure function — no side effects."""
        ...
```

All six detectors (`BaselineGenerator`, `DegradationDetector`, `ModelEfficiencyDetector`, `AnomalyDetector`, `SessionPatternDetector`, `ReworkCorrelationDetector`) implement this protocol. Each is a class with `detect()` and an internal `_confidence()` method. They are instantiated once in `OptimizerModule.start()`.

## Orchestrator

```python
class OptimizerModule(Module):
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._detectors: list[Detector] = []

    async def start(self, context: Context) -> None:
        self._context = context
        self._detectors = [
            BaselineGenerator(),
            DegradationDetector(),
            ModelEfficiencyDetector(),
            AnomalyDetector(),
            SessionPatternDetector(),
            ReworkCorrelationDetector(),
        ]

    async def stop(self) -> None:
        self._context = None
        self._detectors.clear()

    async def shutdown(self) -> None:
        pass

    def _get_measurements(self) -> list[WorkUnit]:
        measurements = (self._context.services.get("pulse.measurements") or (lambda: []))()
        return measurements or []

    def _run_cycle(self) -> list[OptimizationHypothesis]:
        units = self._get_measurements()
        hypotheses: list[OptimizationHypothesis] = []
        for detector in self._detectors:
            hypotheses.extend(detector.detect(units))
        return hypotheses
```

## Service Wiring

```python
@property
def services(self) -> dict[str, Callable]:
    return {
        "optimizer.hypotheses": self._run_cycle,
        "optimizer.baselines": self._get_baselines,
        "optimizer.status": self._get_status,
    }

def _get_baselines(self) -> dict:
    """Return current baseline data (computed on-read)."""
    ...

def _get_status(self) -> dict:
    pulse_connected = "pulse.measurements" in (
        self._context.services if self._context else {}
    )
    hyps = self._run_cycle()
    return {
        "available": True,
        "hypothesis_count": len(hyps),
        "baseline_count": len(self._get_baselines()),
        "pulse_connected": pulse_connected,
    }
```

## Pulse Optionality

`_get_measurements()` uses `context.services.get("pulse.measurements")` which returns `None` when Pulse is absent. The fallback `(lambda: [])()` ensures a callable that returns empty list. Every detector receives `[]` and returns `[]` — no branching per detector.

## Determinism Strategy (R12)

- All detectors use only input data — no random seeds, no wall-clock (except `generated_at`).
- `generated_at` is set via `datetime.now(UTC).isoformat()` at hypothesis creation time — it is the **only** non-deterministic field and declared as such.
- `_cap_underpowered()` uses deterministic thresholds (e.g., `< 3 units → cap at 0.5`).
- Z-score and IQR computations use `statistics` module (deterministic in CPython).
- **Stable output order**: `_run_cycle()` MUST return hypotheses in deterministic order — first grouped by detector (the order detectors are registered), then within each group by `confidence` descending, then by `generated_at` ascending. This guarantees reproducible diffs and predictable test assertions.
- **Test strategy**: run same input twice, assert entire hypothesis list equality.

## Detector Independence

Every detector MUST execute independently. The orchestrator SHALL NOT allow a single detector failure to cascade:

```python
def _run_cycle(self) -> list[OptimizationHypothesis]:
    units = self._get_measurements()
    hypotheses: list[OptimizationHypothesis] = []
    for detector in self._detectors:
        try:
            hypotheses.extend(detector.detect(units))
        except Exception:
            continue  # Isolate failures — available results still returned
    return self._sort_hypotheses(hypotheses)
```

- If one detector raises, the others still produce hypotheses.
- The orchestrator aggregates all available results.

## Detector Purity

Every detector MUST be a pure function:

- **No state writes**: detectors MUST NOT write to `self`, module state, or global state.
- **No direct service access**: detectors MUST NOT call `context.services`, read files, or perform I/O. All input arrives via the `units: list[WorkUnit]` parameter.
- **Input immutability**: detectors MUST NOT mutate the `units` list or any `WorkUnit` object within it.
- **No side effects**: the sole output is `list[OptimizationHypothesis]`.

The `Detector` protocol enforces this by design — the signature `detect(units: list[WorkUnit]) -> list[OptimizationHypothesis]` has no reference to context, services, or external state.

## Confidence Scoring Per Detector

| Detector | Basis | Floor/Cap rules |
|----------|-------|-----------------|
| Degradation | `z-score magnitude / max_z` (sigmoid-mapped) | `<3 data points → cap 0.4` |
| ModelEfficiency | `effect_size / max_effect` | Single model → no hypothesis |
| Anomaly | `1 - (distance / max_distance)` | `<3 points per metric → no hypothesis` |
| SessionPattern | `cluster_size / total` | `<3 total units → no hypothesis` |
| ReworkCorrelation | `correlation_coefficient (abs)` | No rework data → no hypothesis |

All share `_confidence.cap_underpowered(score: float, n: int) → float`.

## File Listing

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/optimizer/__init__.py` | Create | Package init, lazy-import `OptimizerModule` |
| `src/apoch/modules/optimizer/models.py` | Create | Frozen `OptimizationHypothesis` dataclass |
| `src/apoch/modules/optimizer/module.py` | Create | `OptimizerModule` — lifecycle, detector orchestration, 3 services |
| `src/apoch/modules/optimizer/_detectors.py` | Create | `Detector` protocol + all 6 detector implementations |
| `src/apoch/modules/optimizer/_confidence.py` | Create | Shared confidence helpers |
| `src/apoch/modules/__init__.py` | Modify | Add `"optimizer"` to `__all__` |
| `pyproject.toml` | Modify | Add `optimizer` entry point under `apoch.modules` |
| `tests/modules/optimizer/test_detectors.py` | Create | Unit tests for each detector (happy path, empty, partial, determinism) |
| `tests/modules/optimizer/test_module.py` | Create | Lifecycle, service wiring, Pulse optionality, R10 purity |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Each detector | Deterministic input → expected hypothesis shape. Empty input → empty output. Partial data → graceful handling. |
| Unit | `cap_underpowered` | Verify floor/cap logic at boundary values |
| Integration | `OptimizerModule` lifecycle | `start` → `stop` → `shutdown` via Module ABC |
| Integration | Service wiring | 3 duck-typed services registered, return correct types |
| Integration | Pulse optionality | No `pulse.measurements` → empty hypotheses, `pulse_connected: false` |
| Purity | Data immutability | Frozen dataclass + unit input list not mutated |
| Determinism | Full cycle | Same input × 2 calls → identical hypothesis list |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required (new module).

## Open Questions

- [ ] `BaselineGenerator` output — should it be used by other detectors as a shared baseline or re-computed per detector? Current design: re-computed on-read in `_run_cycle()` for purity.
- [ ] Z-score vs IQR as the default for `AnomalyDetector` — IQR is more robust for skewed distributions. Using IQR in v1.
