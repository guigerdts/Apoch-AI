# Design: Oracle — Recommendation Engine

## Technical Approach

Stateless compute module that maps `OptimizationHypothesis` → `list[Recommendation]` on-read. Follows the existing Optimizer/Pulse ABC pattern: `OracleModule` publishes `oracle.recommendations` as a duck-typed service. Core logic lives in a pure `RecommendationEngine` class. Chronicle integration (optional) writes lifecycle events via `chronicle.record`; Guardian/Vision (optional) degrade confidence. No scheduler, background process, or inbound coupling.

## Architecture Decisions

### Decision: Pure engine class + module facade
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Logic in module.py | Couples tests to lifecycle | **Engine is pure, testable without Module ABC** |
| Separate engine.py + models.py | Slight module overhead | Chosen — mirrors Optimizer's separation |

### Decision: Frozen Recommendation dataclass
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Frozen | Immutable per R4 | **Chosen — same pattern as OptimizationHypothesis** |
| Pydantic model | Heavier dep, not needed | Rejected — simple validation, no serialization |

### Decision: Chronicle writes via try/except
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Guard clause + try/except | Chronicle write never blocks | **Chosen — R8 graceful degradation** |
| Async fire-and-forget | Harder to test | Rejected — explicit try/except is testable |

## Data Flow

```
optimizer.hypotheses ──→ RecommendationEngine ──→ list[Recommendation] ──→ sorted output
         │                        │
         └── context.services     │
                     ┌────────────┘
                     │
          Guardian.diagnostics() ──→ confidence degradation (optional)
          Vision.module_state() ───→ confidence degradation (optional)
          chronicle.record() ──────→ lifecycle events (optional, non-blocking)
```

## Data Model

```python
@dataclass(frozen=True)
class Recommendation:
    id: str                        # uuid4.hex
    title: str
    description: str
    priority: Literal["critical", "high", "medium", "low"]
    confidence: float              # 0.0–1.0
    evidence: dict
    justification: str
    dependencies: list[str]
    expiration: str                # ISO 8601
    source_hypotheses: list[str]   # OptimizationHypothesis IDs
    domain: Literal["cost", "time", "rework", "model_efficiency", "session_behavior", "general"]
    status: Literal["active", "accepted", "rejected", "expired"]
    created_at: str                # ISO 8601
```

## Priority Mapping

| Domain | Anomaly | Degradation | Pattern |
|--------|---------|-------------|---------|
| cost | critical | high | medium |
| time | high | high | medium |
| rework | high | high | medium |
| model_efficiency | medium | medium | low |
| session_behavior | low | medium | low |
| default (general) | medium | medium | low |

Confidence bonus: `+1 priority tier` when confidence ≥ 0.9 AND domain is cost/time/rework.

## Status State Machine

```
     active ──→ accepted  (via Chronicle event)
     active ──→ rejected  (via Chronicle event)
     active ──→ expired   (on-read check: created_at + domain_TTL < now)
```

Domain TTL defaults: critical=1h, high=4h, medium=8h, low=24h. Configurable via `config["oracle"]["ttl"]`.

## Chronicle Integration

Events written via `chronicle.record` (async, non-blocking, caught errors):

| Event Type | When | Payload |
|------------|------|---------|
| `recommendation_generated` | On `oracle.recommendations()` call | Full `Recommendation` fields |
| `recommendation_accepted` | External call to `accept()` | rec ID, timestamp |
| `recommendation_rejected` | External call to `reject()` | rec ID, reason, timestamp |
| `recommendation_outcome` | External call to `record_outcome()` | rec ID, outcome, metadata |

On read: if Chronicle is available, Oracle queries past recommendation events and merges status. If absent, all recs are ephemeral `active`.

## Determinism Strategy (R10)

1. **No randomness** in mapping — hypothesis fields fully determine priority/confidence
2. **Sort tiebreaker**: `priority` (enum ordinal) → `-confidence` → `created_at` → `id` (lexicographic)
3. `created_at` and `id` are the only time/random-dependent fields (permitted by R10)
4. Stable sort on a canonical sort key tuple

## Service Wiring

```python
@property
def services(self) -> dict[str, Callable]:
    return {"oracle.recommendations": self._compute_recommendations}
```

Signature: `() -> list[Recommendation]`. Returns empty list if Optimizer absent.

## Standalone Mode

- No context → `context.services.get("optimizer.hypotheses")` → falls through to `[]`
- No Chronicle → skip write, skip read-reconstruction
- No Guardian → confidence used as-is from hypothesis
- No Vision → no additional degradation

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/oracle/__init__.py` | Create | Lazy-import OracleModule (per module pattern) |
| `src/apoch/modules/oracle/models.py` | Create | `Recommendation` frozen dataclass, `RecommendationStatus` StrEnum |
| `src/apoch/modules/oracle/engine.py` | Create | Pure `RecommendationEngine` — mapping, sorting, expiration |
| `src/apoch/modules/oracle/module.py` | Create | `OracleModule` (Module ABC) — lifecycle + services + Chronicle wiring |
| `src/apoch/modules/__init__.py` | Modify | Add `oracle` to `__all__` |
| `pyproject.toml` | Modify | Add `oracle = "apoch.modules.oracle.module:OracleModule"` entry point |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| unit | `RecommendationEngine` mapping | Pure function: input hyp list → assert rec fields + sort order |
| unit | Priority mapping table | All (domain × type) combos produce correct priority |
| unit | Expiration logic | Fixed clock: rec within TTL → active, past TTL → expired |
| unit | Determinism | Same input × 2 calls → identical output |
| unit | Empty/missing input | None → [], empty → [], partial → valid rec with degraded confidence |
| integration | `OracleModule` with mocked `context.services` | Optimizer present/absent, Chronicle present/absent |
| integration | Guardian confidence degradation | mock guardian.diagnostics → verify confidence lowered |
| integration | Chronicle event writing | mock chronicle.record → verify event payload |
| integration | Chronicle read-reconstruction | Mock past events → verify merged status |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Oracle is read-only compute (R9).

## Migration / Rollout

## Cross-Cutting Constraints

### Constraint A: Engine has zero side effects

`RecommendationEngine` MUST NOT know about `context`, Chronicle, or any service. Its interface is pure:

```python
class RecommendationEngine:
    def generate(
        self,
        hypotheses: list[OptimizationHypothesis],
        health: dict | None = None,
    ) -> list[Recommendation]: ...
```

- Input: resolved hypotheses + optional health data.
- Output: `list[Recommendation]`.
- No service discovery, no I/O, no state mutation.

### Constraint B: OracleModule is the sole adapter

`OracleModule` discovers services, builds the engine context, persists to Chronicle (if available), and exposes `oracle.recommendations`. It MUST NOT contain recommendation rules, priority logic, or domain knowledge — those belong exclusively in `RecommendationEngine`.

```python
class OracleModule(Module):
    @property
    def services(self) -> dict[str, Callable]:
        return {"oracle.recommendations": self._get_recommendations}

    def _get_recommendations(self) -> list[Recommendation]:
        hyps = self._context.services.get("optimizer.hypotheses", lambda: [])()
        health = self._get_health()   # optional Guardian/Vision enrichment
        recs = self._engine.generate(hyps, health)
        self._try_record(recs)         # optional Chronicle persistence
        return recs
```

## Migration / Rollout

No migration required. Oracle is a new module with zero inbound coupling. Add entry point, register in `__init__.py`, nothing else references it. Rollback is delete entry point + delete module dir.

## Open Questions

None.

## Test File Structure

```
tests/
└── apoch/
    └── modules/
        └── oracle/
            ├── test_models.py         # Recommendation factory/repr/immutability
            ├── test_engine.py         # Pure mapping, sorting, expiration, determinism
            └── test_module.py         # Lifecycle, services, Chronicle/Guardian integration
```
