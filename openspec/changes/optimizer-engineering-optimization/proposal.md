# Proposal: Optimizer — Engineering Optimization Intelligence

## Intent

Engineering teams accumulate sessions, code structure, and productivity data with no systematic mechanism to detect improvement patterns — redundant context, inefficient model usage, anomalous session behavior, and costly rework cycles go unnoticed. Optimizer is the Engineering Optimization Intelligence module that detects patterns, anomalies, and opportunities for improvement in engineering workflows without prescribing actions.

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| Detect optimization patterns from available data | Ranking hypotheses by business impact (Oracle domain) |
| Generate structured `OptimizationHypothesis` per finding | Recommending or executing actions |
| Expose services: `"optimizer.hypotheses"`, `"optimizer.baselines"`, `"optimizer.status"` | Calling Pulse's `record()`, `save()`, or any write API |
| Module ABC lifecycle (Chronicle/Guardian/Vision/Pulse pattern) | Storing session content, identity, or system metrics |
| Duck-typed Pulse data consumption via `context.services.get("pulse.measurements")` | Modifying project files or code structure |
| | Public sub-module API — internal detectors only |

## Capabilities

### New
- `optimizer-engineering-optimization`: Pattern, anomaly, and opportunity detection in engineering workflows — generates `OptimizationHypothesis` from available data.

### Modified
- None

## Approach

1.  `OptimizerModule` exposes three services via `@property services`: `"optimizer.hypotheses"`, `"optimizer.baselines"`, `"optimizer.status"`.
2.  Internal detectors (DegradationDetector, ModelEfficiencyDetector, AnomalyDetector, SessionPatternDetector, ReworkCorrelationDetector) each produce typed hypotheses — these are implementation details, not public components.
3.  Pulse data read via `context.services.get("pulse.measurements")` — graceful degradation to empty set.
4.  All hypothesis generation is stateless read-only analysis. Optimizer never mutates data.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/apoch/modules/optimizer/` | New | `OptimizerModule` + internal detectors |
| `src/apoch/modules/__init__.py` | Modified | Add `"optimizer"` to `__all__` |
| `pyproject.toml` | Modified | Add `optimizer` entry point under `apoch.modules` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Hypothesis quality low in v1 | Med | Explicit schema; iterable detector interface |
| Boundary creep vs Oracle | Low | Contract: hypotheses, not recommendations |
| Over-engineered detectors | Med | Ship v1 with simplest plausible detection |

## Rollback

Remove optimizer module directory, registration, and entry point. No module depends on Optimizer. Zero-revert surface.

## Dependencies

None mandatory. Pulse is optional — Optimizer returns empty hypothesis set when `"pulse.measurements"` is absent.

## Success Criteria

- [ ] `OptimizerModule` follows Module ABC lifecycle (`start`/`stop`/`shutdown`)
- [ ] Three services exposed: `"optimizer.hypotheses"`, `"optimizer.baselines"`, `"optimizer.status"`
- [ ] At least one internal detector produces a valid `OptimizationHypothesis`
- [ ] Returns empty hypothesis set when Pulse is absent
- [ ] Never calls Pulse's `record()`, `save()`, or any write-capable method
- [ ] All hypotheses carry typed `type`, `domain`, `confidence`, `evidence`, `affected_scope`, and `generated_at`
