# Design: Pulse — Engineering Productivity Intelligence

## Technical Approach

Pulse follows the same Module ABC pattern as Chronicle/Guardian/Vision. Internally, four components with clear SRP boundaries: **Measurement** collects raw data, **Storage** persists it, **Analysis** derives trends and rework, **Integration** exposes data to Optimizer/Oracle through optional interfaces. No component depends on another module.

## Architecture Decisions

| Decision | Option | Tradeoff | Choice |
|----------|--------|----------|--------|
| Component split | 2 (store + module) vs 4 (measure + store + analyze + integrate) | Simpler but monolithic vs SRP-clean | 4 components — R11 requires explicit integration isolation |
| Integration pattern | Direct import vs duck-typed service | Tighter coupling vs optional at runtime | Duck-typed `@property services` — matches Chronicle pattern |
| Storage abstraction | ABC vs single class | YAGNI vs future flexibility | Single class in v1 — extract ABC when a second backend appears |
| Analysis timing | On-write vs on-read vs scheduled | Freshness vs complexity | On-read (idempotent, no scheduler needed) |
| Measurement mode | Mutable vs append-only | Flexibility vs auditability | **Append-only** — measurements are immutable facts. Analysis derives from them, never modifies them. Consistency with Chronicle's event model. |

## Data Flow

```
SessionData → Measurement → Storage ─→ Analysis → TrendData
                                   │
                                   ├→ Integration → Optimizer (optional)
                                   │              → Oracle (optional)
                                   │
                                   └→ R11 gate: all paths from Storage ↗
                                      to other modules are optional.
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/pulse/__init__.py` | Create | Package init, exports `PulseModule` |
| `src/apoch/modules/pulse/module.py` | Create | `PulseModule(Module)` — lifecycle + SRP component wiring |
| `src/apoch/modules/pulse/storage.py` | Create | `PulseStore` — internal measurement persistence |
| `src/apoch/modules/pulse/models.py` | Create | `WorkUnit`, `Measurement`, `TrendPoint` dataclasses |
| `src/apoch/modules/__init__.py` | Modify | Add `"pulse"` to `__all__` |
| `pyproject.toml` | Modify | Add `pulse` entry point under `apoch.modules` |

## Interfaces / Contracts

### Internal — MeasureMeasurementInput

```python
@dataclass(frozen=True)
class MeasurementInput:
    session_id: str
    work_unit_id: str
    model: str
    tokens_input: int
    tokens_output: int
    wall_clock_s: float
    cost: Decimal | None       # Optional — model must have a price
```

### Internal — AnalysisInput

```python
@dataclass
class AnalysisInput:
    work_unit: WorkUnit
    window_days: int            # Rework window
```

### Optional — Integration Contracts

```python
# Published as a cross-module service (duck-typed, like Chronicle)
# key: "pulse.measurements"
# signature: async (filter: PulseFilter) -> Measurements
# optional: Yes — Optimizer/Oracle degrade gracefully if absent.
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | MeasurementInput → Storage | Isolated `PulseStore` tests with in-memory backing |
| Unit | Rework calculation | Deterministic input → expected % |
| Unit | Trend derivation | 2+ work units → correct trend shape |
| Integration | `PulseModule` lifecycle | `start` → `stop` → `shutdown` via Module ABC |
| Integration | Cross-module service | Verify `@property services` exposes measurement data |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required (new module).

## Open Questions

- [ ] Should Pulse publish a per-measurement-arrival event for Chronicle (optional enrichment)?
