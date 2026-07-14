# Proposal: Oracle Recommendation Engine

## Intent

Bridge the gap between detection and action — the 7th and final Engineering Intelligence Layer module. Optimizer produces hypotheses ("what is probably happening"). Oracle translates them into actionable, prioritized, confidence-scored recommendations ("what to do about it"). Oracle consumes hypotheses, NEVER measurements, and NEVER executes actions.

## Scope

### In Scope
- `Recommendation` data model with id, title, description, priority, confidence, evidence, justification, dependencies, expiration, source_hypotheses, domain, created_at
- Hypothesis-to-recommendation mapping engine (type/domain/confidence → priority/action guidance)
- Priority model: critical/high/medium/low sorted by impact + urgency + confidence
- Expiration policy: default TTL per domain (configurable)
- Chronicle lifecycle events: `recommendation_generated`, `_accepted`, `_rejected`, `_outcome` via `chronicle.record`
- Read-side reconstruction: past outcomes queried from Chronicle for context
- Ephemeral mode: full operation without Chronicle (no persistence, no history)
- Optional Guardian/Vision integration: module health degrades recommendation confidence

### Out of Scope
- Action execution — Oracle recommends, NEVER executes (no config changes, no shell, no MCP mutations)
- Pulse measurement ingestion — Oracle NEVER reads `pulse.measurements` directly
- Hypothesis re-computation — Oracle consumes Optimizer output as-is, never re-derives
- Config modification — Oracle does not change module or system configuration
- Persistent storage — Chronicle owns persistence; Oracle owns the model and logic only
- Other module modification — Oracle never writes to Pulse, Optimizer, Guardian, or Vision

## Capabilities

### New Capabilities
- `module-oracle`: Recommendation engine — hypothesis-to-recommendation mapping, priority/confidence scoring, expiration policy, Chronicle lifecycle events, ephemeral degradation, optional Guardian/Vision health integration

### Modified Capabilities
- None — Oracle is a pure read-only consumer. No existing spec changes at behavioral level.

## Approach

Stateless compute module with optional Chronicle persistence. Oracle reads `optimizer.hypotheses` as primary input, applies mapping rules, and returns `list[Recommendation]` sorted by priority (critical first) then confidence descending. When Chronicle is available, Oracle writes lifecycle events via `chronicle.record` into `ActivityEvent.payload` (no schema changes needed). Without Chronicle, recommendations are ephemeral — computed on read, no persistence. Oracle MAY read Guardian diagnostics and Vision module_state to degrade confidence on unhealthy dependencies.

Oracle follows the same service pattern as Optimizer/Pulse/Chronicle: publishes `oracle.recommendations` as a cross-module callable, registers via `pyproject.toml` entry point, and follows the Module ABC lifecycle.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/apoch/modules/oracle/` | New | Entire Oracle package — models, engine, services |
| `pyproject.toml` | Modified | Add `oracle` entry point under `apoch.modules` |
| `src/apoch/modules/__init__.py` | Modified | Add `oracle` to `__all__` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Chronicle unavailable | Low | Ephemeral mode — recommendations returned but not stored |
| Optimizer unavailable | Low | Return empty list gracefully, no crash |
| Scope creep into Optimizer territory | Med | Code review gate: Oracle never reads Pulse or runs detectors |
| Circular dep (Oracle → Chronicle) | Low | Chronicle does not import Oracle — no circular path possible |

## Rollback Plan

1. Remove `oracle` entry point from `pyproject.toml`
2. Remove `oracle` from `src/apoch/modules/__init__.py`
3. Delete `src/apoch/modules/oracle/` directory
4. Chronicle events (if any were written) remain — no data loss, no schema impact

No other modules depend on Oracle — zero inbound coupling. Complete rollback with no downstream impact.

## Dependencies

- `optimizer.hypotheses` service (optional — empty list if absent)
- `chronicle.record` service (optional — ephemeral mode if absent)
- Guardian `diagnostics()` + Vision `module_state()` (optional — confidence enrichment)

## Success Criteria

- [ ] Oracle produces `list[Recommendation]` from `optimizer.hypotheses` with correct priority/confidence sorting
- [ ] Chronicle lifecycle events write and reconstruct on read
- [ ] Oracle returns empty list gracefully when Optimizer unavailable
- [ ] Oracle returns valid recommendations without Chronicle (ephemeral mode)
- [ ] Guardian health data degrades recommendation confidence when modules are failing
