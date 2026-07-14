# Proposal: Pulse — Engineering Productivity Intelligence

## Intent

Coding agents operate in session isolation — no accumulated cost data, no model efficiency comparison, no rework trends, no productivity visibility. Engineering teams lack any window into the economics of AI-assisted development.

Pulse is the Engineering Productivity Intelligence module of the Engineering Intelligence Layer. It measures token consumption, monetary cost, time investment, model efficiency, and rework patterns across sessions, PRs, and features.

**Core constraint**: Pulse measures — does not optimize, recommend, govern, or observe infrastructure. Measures → Optimizer interprets → Oracle recommends.

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| Data ownership boundaries for Pulse | APIs, CLI, events, storage schema |
| Metrics Pulse collects exclusively | System profiling (Vision domain) |
| Data relationships with Optimizer/Oracle | Event recording (Chronicle domain) |
| V1 acceptance criteria | Policy enforcement (Guardian domain) |
| | Code optimization (Optimizer domain) |
| | Recommendations (Oracle domain) |

## Capabilities

### New
- `pulse-productivity-intelligence`: Engineering productivity measurement — tokens, cost, time, model, efficiency, rework, trends. Exclusive owner of engineering economics data.

### Modified
- None (Pulse is a new module)

## Approach

1. Accept measurement data from sessions and optional Chronicle.
2. Store raw productivity metrics (tokens, time, cost, model, rework).
3. Expose to Optimizer (interpretation) and Oracle (context).
4. Never interpret, optimize, or recommend.
5. Never store content, identity, or system metrics.

Implementation details (storage, APIs, CLI, events, formats) belong to Spec and Design.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Overlap with Vision metrics | Low | Clear system vs. engineering boundary |
| Coupling to Chronicle | Med | Pulse works standalone; Chronicle optional |
| Interpretation creep | Low | Contract: measures vs. interprets vs. recommends |
| Privacy (session content) | Low | Explicit NEVER store rule |

## Rollback

Remove Pulse module directory, registration, and data store. Core (Engine) has zero Pulse dependencies. No other module affected.

## Dependencies

None mandatory. Optional Chronicle integration for enriched event attribution.

## Success Criteria

- [ ] Tokens per work unit (task/PR/feature) collected and stored.
- [ ] Monetary cost attributed via configurable model pricing.
- [ ] Wall-clock time per work unit tracked.
- [ ] Model identifier per work unit reported.
- [ ] Rework % calculated (lines modified after initial implementation).
- [ ] Trend data available over project timeline.
- [ ] Optimizer can read Pulse data for improvement detection.
- [ ] Oracle can read Pulse data for economic context.
- [ ] No session content, identity, or system metrics stored.
- [ ] All measurements persist across sessions.
