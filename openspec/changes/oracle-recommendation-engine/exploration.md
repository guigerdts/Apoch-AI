# Oracle — Recommendation Engine: Exploration

## Current State

The Engineering Intelligence Layer has 6 modules:

| Module | Role | Exposes Services |
|--------|------|------------------|
| **Chronicle** | Persistent event store | `chronicle.record` (write) |
| **Pulse** | WorkUnit measurements (productivity) | `pulse.measurements` (read) |
| **Optimizer** | Hypothesis generation (detection layer) | `optimizer.hypotheses`, `optimizer.baselines`, `optimizer.status` |
| **Guardian** | Exception isolation / diagnostics | None (consumed by registry) |
| **Vision** | Structured logging / observability | None (consumes `chronicle.record`) |
| **Oracle** | **Does not exist yet** | — |

The architecture was designed from day one with Oracle as the 7th module (see the original exploration at `openspec/changes/diseñar la arquitectura base de Apoch-AI/exploration.md`, line 192: `oracle/` directory). Oracle is the final link in the chain:

```
Chronicle (facts) → Pulse (measurements) → Optimizer (hypotheses) → Oracle (recommendations)
```

### What Optimizer produces

`OptimizerModule` runs 6 detectors (BaselineGenerator, DegradationDetector, ModelEfficiencyDetector, AnomalyDetector, SessionPatternDetector, ReworkCorrelationDetector) and returns `OptimizationHypothesis` objects. Each hypothesis has:

- **type**: `pattern` | `anomaly` | `opportunity`
- **domain**: `cost` | `time` | `rework` | `model_efficiency` | `session_behavior`
- **confidence**: `float` (0.0–1.0)
- **evidence**: `dict` — detector-specific supporting data
- **affected_scope**: `str` — human-readable scope description
- **generated_at**: `str` — ISO 8601 timestamp

Key constraint from Optimizer spec: **"Optimizer NEVER recommends, prescribes, or suggests specific actions. It only produces hypotheses."** (Spec §Constraints). This is the explicit gap Oracle fills.

### What Pulse produces

`PulseModule` stores and exposes `WorkUnit` objects with:

- `id`, `session_id`, `model`
- `tokens_input`, `tokens_output`, `cost`, `wall_clock_s`
- `created_at`, `completed_at`

Exposed via `pulse.measurements` service (read-only list query). No rework fields currently (rework_rate is computed on-demand as a float).

### What Chronicle, Guardian, Vision expose

- **Chronicle**: SQLite-backed `ActivityEvent` store. Service: `chronicle.record` (write). Has `query()`, `prune()`, `stats()` methods exposed as MCP tools but not as cross-module services.
- **Guardian**: Exception boundaries + diagnostics. No services published. Diagnostics accessed via `diagnostics()` method calls.
- **Vision**: NDJSON logging + ring buffer. No services published. Query via `recent()`, `module_state()`, `module_config()`, `system_info()` MCP tool methods.

### Module registration pattern

Modules register via `[project.entry-points."apoch.modules"]` in `pyproject.toml`. The `ModuleRegistry` discovers them by entry point group, loads on demand, and populates `Context.services` from each module's `@property services` duck-typed dict. Oracle's entry point must be added to `pyproject.toml`.

---

## Q1: What exclusive problem does Oracle solve?

**Oracle is the bridge between detection and action.** Optimizer tells you *what is probably happening* (hypotheses). Oracle tells you *what to do about it* (recommendations). Without Oracle:

1. **Hypotheses are inert.** They exist in memory as `OptimizationHypothesis` objects but nobody acts on them. They surface potential issues (cost degradation, model inefficiency, session patterns) but provide no actionable path forward.

2. **No prioritization.** Optimizer returns hypotheses sorted by detector order → confidence desc → timestamp asc. There's no weighting by business impact, urgency, or cost of inaction. A minor anomaly with 0.9 confidence sorts above a critical rework pattern with 0.8 confidence.

3. **No decision support.** "Model X has 2.3x the rework of Model Y" — so what? Should you switch models? Investigate the root cause? Add monitoring? Optimizer cannot answer these.

4. **No feedback loop.** If someone acts on a hypothesis, there's no record of whether that was the right call. Oracle provides the feedback loop: recommendation → action → outcome → learning.

5. **No expiration or staleness.** Hypotheses are snapshots. A 3-day-old hypothesis about a session pattern is meaningless if the schedule changed. Recommendations need lifespans.

**The gap:** Between "what's happening" (Optimizer) and "what to do" (human or automation) lives a layer of interpretation, prioritization, risk assessment, and structured guidance. That is Oracle's exclusive domain.

---

## Q2: What is Oracle's canonical input?

### Primary source: `optimizer.hypotheses`

Oracle's **primary input** is the list of `OptimizationHypothesis` objects from `optimizer.hypotheses`. Why?

1. **Optimizer is already the aggregation layer.** It processes raw Pulse measurements through 6 detectors and produces structured, confidence-scored findings. Oracle should not re-derive what Optimizer already computed.
2. **Separation of concerns.** If Oracle also consumed Pulse directly, it would duplicate Optimizer's analysis logic and create coupling to raw measurement schemas.
3. **Stable contract.** `OptimizationHypothesis` is a frozen dataclass with explicit fields. The service key is registered: `"optimizer.hypotheses"`.

### Does Oracle consume Pulse directly?

**No — never directly.** Oracle works at the recommendation layer, not the measurement layer. If Oracle needs measurement-derived context that Optimizer doesn't provide (e.g., raw trend data for "how urgent is this"), the correct path is:

1. Add a new Optimizer detector or augment existing hypothesis evidence
2. Oracle reads the enriched hypothesis

Exception: if Oracle needs *recommendation-specific* data that is not hypothesis-related (e.g., verifying recommendation history from Chronicle), that is a different concern.

### Optional context sources

Oracle MAY consume these as supplemental context, but they are strictly optional:

| Source | Service / Method | What Oracle uses it for |
|--------|-----------------|------------------------|
| **Chronicle** | `chronicle.query()` (MCP tool) | Past recommendation outcomes — "did we recommend this before and was it rejected?" |
| **Guardian** | `guardian.diagnostics()` (method) | Module health data — "is a module failing? Should we recommend intervention?" |
| **Vision** | `vision.recent()`, `vision.module_state()` (MCP tools) | Recent errors or degraded modules — "is the system itself healthy enough to trust recommendations?" |
| **Pulse** | `pulse.measurements` | **Never directly.** Any Pulse-derived context goes through Optimizer first. |

The key rule: **Oracle reads from Chronicle (past decisions) and Guardian/Vision (system health), but never from Pulse directly.**

---

## Q3: What is Oracle's output?

### Recommendation — the canonical output

```python
@dataclass(frozen=True)
class Recommendation:
    """A structured, actionable recommendation derived from hypotheses."""
    
    id: str                              # uuid
    title: str                           # Short human-readable title
    description: str                     # What to do and why
    priority: Literal["critical", "high", "medium", "low"]
    confidence: float                    # 0.0–1.0 (derived from hypothesis + context)
    evidence: dict                       # Supporting data (hypotheses, diagnostics, chronology)
    justification: str                   # Why this recommendation exists
    dependencies: list[str]              # Preconditions for this recommendation
    expiration: str                      # ISO 8601 — when this recommendation becomes stale
    source_hypotheses: list[str]         # IDs of OptimizationHypotheses that drove this
    domain: str                          # Same domains as hypotheses + "system_health"
    created_at: str                      # ISO 8601
```

### Minimum fields

| Field | Why required |
|-------|-------------|
| `title` | Human-readable identification |
| `description` | Actionable guidance |
| `priority` | Urgency triage (critical → low) |
| `confidence` | Trustworthiness (0.0–1.0) |
| `evidence` | Traceable supporting data |
| `justification` | Reasoning chain |
| `dependencies` | Preconditions that must be met |
| `expiration` | When the rec is no longer relevant |
| `source_hypotheses` | Links back to Optimizer output |
| `domain` | Categorization |
| `created_at` | Temporal ordering |

### Generated outputs

Oracle generates `list[Recommendation]` sorted by priority (critical first) then confidence descending. Recommendations are ephemeral — computed on read, not persisted by default (unless recommendation tracking is enabled).

---

## Q4: What must Oracle NEVER do?

### Hard boundaries (non-negotiable)

| Boundary | Why |
|----------|-----|
| **No action execution** | Oracle recommends; it NEVER executes. No config changes, no file writes, no shell commands, no MCP tool calls that mutate state. |
| **No config modification** | Oracle does not change module configs, enable/disable features, or alter system behavior. |
| **No persistence in other modules** | Oracle does NOT write to Pulse's store, Chronicle's event log, or any other module's storage. Its own recommendation history is the only data it persists (see Q7). |
| **No re-computing hypotheses** | Oracle consumes Optimizer output as-is. It does not re-derive `OptimizationHypothesis` from raw data. |
| **No measurement ingestion** | Oracle never calls `pulse.record()` or any data-ingestion path. |
| **No bypassing Guardian** | If Guardian has marked a module as FAILED, Oracle respects that state and adjusts recommendations accordingly. |

### Design principle

Oracle is **advisory-only**. It operates at the same altitude as Optimizer (read-only analysis) but one level higher in the abstraction stack. The only state Oracle may own is its own recommendation history.

---

## Q5: How does Oracle differ from Optimizer?

| Dimension | Optimizer | Oracle |
|-----------|-----------|--------|
| **Question answered** | "What is probably happening?" | "What should we do about it?" |
| **Input** | Pulse measurements → WorkUnits | Optimizer hypotheses + optional system context |
| **Output** | `OptimizationHypothesis` (detection) | `Recommendation` (prescription) |
| **Decision level** | Statistical/heuristic | Prioritization + action guidance |
| **Temporal scope** | Point-in-time snapshot | Recommendations have expirations |
| **Context scope** | Measurements only | Hypotheses + system health + history |
| **State** | Stateless (read-only compute) | Can track recommendation history |
| **Confidence source** | Detector-specific statistical scoring | Multi-factor: hypothesis confidence + system health + historical outcomes |
| **Priority** | Detector order → confidence → time | Business impact + urgency + risk |

### Analogy

- **Pulse** = raw sensor data (temperature readings)
- **Optimizer** = diagnostic system ("temperature is 2σ above baseline, engine degrading")
- **Oracle** = maintenance advisor ("reduce power by 10%, schedule inspection within 24 hours")

Optimizer tells you the engine is hot. Oracle tells you what to do about it.

---

## Q6: What role does Guardian play?

Guardian provides **exception isolation and diagnostics**. Its influence on Oracle is:

### Direct influence

1. **Module health filtering.** If Guardian's diagnostics show a module (e.g., Pulse) has failed, Oracle should:
   - Reduce confidence of recommendations that depend on that module's data
   - Add `dependencies: ["pulse must be healthy"]` to affected recommendations
   - Potentially generate system-health recommendations ("Pulse module has failed N times in 24h")

2. **Recommendation degradation.** A recommendation derived from hypotheses that came from a failing module should be explicitly flagged as degraded.

### Not a policy engine

Guardian does NOT provide business rules, access control lists, or policy filtering. Guardian's role is **runtime health and exception boundaries**, not governance of what recommendations are allowed. If Oracle needs policy rules (e.g., "never recommend model-switching for production environments"), those belong in Oracle's own configuration, not Guardian.

### Integration pattern

```
Oracle
  ├── reads hypotheses via context.services["optimizer.hypotheses"]
  ├── reads diagnostics via context.registry.loaded["guardian"].diagnostics()
  └── reads module states via context.registry.loaded["vision"].module_state()
```

Oracle consumes Guardian's diagnostics output but does NOT use Guardian's `protect()` method — that's for the registry's lifecycle management, not cross-module data access.

---

## Q7: What persistent value does Oracle add?

Oracle's **optional-but-recommended** persistence layer is a recommendation history store. This adds:

### What it tracks

| Data | Purpose |
|------|---------|
| Generated recommendations | Snapshot of what was recommended and when |
| Acceptance/rejection records | Who accepted or rejected, when, and why |
| Effectiveness outcomes | Was the recommendation acted on? Did it work? |
| Quality evolution | Are recommendations getting better over time? (confidence calibration, acceptance rate trends) |

### Value

1. **Learning loop.** Without history, every recommendation cycle is blind. With history, Oracle can:
   - Track which hypotheses most often lead to actionable recommendations
   - Detect recurring patterns ("this is the 5th time we've seen this degradation pattern")
   - Calibrate confidence based on historical acceptance/rejection rates

2. **Audit trail.** Who saw which recommendation? What did they decide? Non-repudiation and traceability.

3. **Quality metrics.** Recommendation acceptance rate, mean time to acceptance, effectiveness score — all feed back into Oracle's own confidence scoring.

### Write vs Read

| Data | Oracle writes | Oracle reads |
|------|:---:|:---:|
| Recommendation history | ✅ | ✅ |
| Acceptance/rejection records | ✅ | ✅ |
| Effectiveness feedback | ✅ | ✅ |
| Module diagnostics | ❌ | ✅ (from Guardian) |
| Module states | ❌ | ✅ (from Vision) |
| Hypotheses | ❌ | ✅ (from Optimizer) |
| Raw measurements | ❌ | ❌ |
| Configs | ❌ | ❌ |
| Events | ❌ | ✅ (from Chronicle) |

---

## Q8: What data does Oracle own?

### Oracle WRITES (owns exclusively)

| Data | Store | Purpose |
|------|-------|---------|
| Recommendation records | Chronicle or dedicated store | History of what was recommended |
| Acceptance/rejection events | Chronicle | Audit trail of decisions |
| Effectiveness feedback | Chronicle | Learning data for quality improvement |

All writes go to **Chronicle** as `ActivityEvent` objects (typed as `recommendation_generated`, `recommendation_accepted`, `recommendation_rejected`, `recommendation_outcome`). This avoids Oracle needing its own database.

If Chronicle is unavailable, Oracle operates in **ephemeral mode** — recommendations are computed and returned but not persisted.

### Oracle CONSUMES (read-only)

| Data | Source | How |
|------|--------|-----|
| OptimizationHypotheses | `optimizer.hypotheses` service | Primary input |
| Module diagnostics | `guardian.diagnostics()` | Optional context |
| Module states | `vision.module_state()` | Optional context |
| Past recommendation events | `chronicle.query()` | Optional context |
| Module status | `optimizer.status` | Optional context |

### Oracle NEVER touches

- Pulse measurements directly
- Module configs
- Filesystem (no logging, no config, no state files)
- External APIs or commands
- Other modules' internal state

---

## Affected Areas

| Path | Why it's affected |
|------|------------------|
| `src/apoch/modules/oracle/` | **New module** — entire Oracle package needs creation |
| `pyproject.toml` | Add `oracle` entry point under `[project.entry-points."apoch.modules"]` |
| `src/apoch/modules/__init__.py` | Add `oracle` to `__all__` |
| `src/apoch/modules/optimizer/models.py` | Oracle imports `OptimizationHypothesis` (already public in `__all__`) |
| `src/apoch/modules/chronicle/models.py` | Oracle writes recommendation events to Chronicle (optional) |
| `openspec/specs/module-oracle/` | **New spec** — Oracle specification |
| `openspec/designs/module-oracle/` | **New design** — Oracle technical design |

---

## Approaches

### 1. Oracle as stateless computation module

Produce recommendations on every call by reading hypotheses from Optimizer. No persistence layer. Output is purely ephemeral.

- **Pros**: Simplest to build. No storage dependency. No Chronicle coupling. Follows Optimizer's pure-read pattern.
- **Cons**: No history, no learning, no audit trail. Every session is a fresh start. Cannot track recommendation effectiveness.
- **Effort**: Low

### 2. Oracle with Chronicle-backed recommendation history (RECOMMENDED)

Oracle produces recommendations ephemerally by default. When Chronicle is available, Oracle writes recommendation lifecycle events (generated, accepted, rejected, outcome) to Chronicle's `chronicle.record` service. **Chronicle is the sole owner of persistence. Oracle reconstructs its state on-read from Chronicle events.** Oracle owns the recommendation model and decision logic — NOT the storage.

- **Pros**: Full audit trail. Learning loop possible. No new database. Chronicle is already a dependency. Consistent with how other modules consume Chronicle (on-read reconstruction).
- **Cons**: Slightly more complex. Requires Chronicle for persistence (degrades gracefully to ephemeral mode).
- **Effort**: Medium

### 3. Oracle with dedicated SQLite store

Oracle gets its own SQLite database (like Chronicle has) for recommendation history, independent of Chronicle.

- **Pros**: Full isolation from Chronicle's schema. No risk of event-store design constraining recommendation logic.
- **Cons**: Duplicates Chronicle's storage pattern. Violates "Chronicle is the persistence layer" principle. Another database to manage. Another schema to version.
- **Effort**: High

---

## Recommendation

**Approach 2: Chronicle-backed persistence (Oracle reads, Chronicle owns).**

Rationale:

1. **Chronicle is the persistence owner, Oracle is the consumer.** Oracle writes events via `chronicle.record` and reads them back on-demand. Chronicle remains the single system of record.
2. **Graceful degradation.** If Chronicle is absent, Oracle returns ephemeral recommendations. No hard dependency.
3. **Learning loop enabled.** History of recommendations → acceptance → outcomes enables quality tracking and confidence calibration.
4. **No new database.** Chronicle's existing `ActivityEvent` model covers Oracle's needs.
5. **Consistent with EI Layer pattern.** Chronicle = facts. Pulse = measurements. Optimizer = hypotheses. Oracle = recommendations. Each module owns its model, Chronicle owns persistence.
6. **Clean separation.** Oracle NEVER writes to Pulse, Optimizer, Guardian, or Vision. Oracle NEVER reads Pulse directly. Oracle NEVER executes actions.

### What needs Chronicle schema extension

The `ActivityEvent.payload` (a generic `dict`) already supports arbitrary structured data. Oracle can store recommendation records as:

```python
ActivityEvent(
    source="oracle",
    event_type="recommendation_generated",  # or _accepted, _rejected, _outcome
    details={
        "recommendation_id": "...",
        "title": "...",
        "priority": "high",
        "confidence": 0.85,
        # ... full Recommendation fields
    }
)
```

No Chronicle schema changes needed — `payload` is already flexible.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Chronicle unavailable** | No persistence for rec history | Ephemeral mode — recommendations returned but not stored. Log warning. |
| **Optimizer unavailable** | No hypotheses → empty recommendations | Return empty list gracefully. No crash. |
| **Recommendation overload** | Too many low-value recommendations | Confidence floor (min 0.3) and priority filter (drop "low" by default). Configurable threshold. |
| **Circular dependency** | Oracle → Chronicle, but Chronicle uses Oracle | Oracle only reads from Chronicle. Chronicle does not import Oracle. No circular dep. |
| **Scope creep into Optimizer territory** | Oracle starts re-deriving hypotheses | Enforce in code review: Oracle's `_generate_recommendations()` never reads Pulse or runs analysis. |

---

## Ready for Proposal

**Yes.** All 8 questions answered. The boundaries are well-understood. Both Optimizer and Chronicle have stable contracts that Oracle can target. The approach (stateless compute + Chronicle-backed persistence) is low-risk and follows existing patterns.

### What the Proposal phase should cover

1. **Recommendation generation algorithm**: How do hypotheses become recommendations? Mapping rules from hypothesis type/domain/confidence to recommendation priority/action.
2. **Priority scoring model**: How critical/high/medium/low is determined (combination of confidence + impact + urgency).
3. **Expiration policy**: Default TTL per recommendation type. Configurable.
4. **Chronicle integration**: Event types and payload schema for recommendation persistence.
5. **Degradation rules**: How module health (from Guardian) and system state (from Vision) affect recommendation confidence.
6. **Configuration surface**: Priority thresholds, minimum confidence, expiration defaults, enabled/disabled recommendation types.
