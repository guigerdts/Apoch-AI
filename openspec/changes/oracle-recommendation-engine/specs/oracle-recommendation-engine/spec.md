# Oracle — Recommendation Engine Specification

## Purpose

Oracle translates `OptimizationHypothesis` objects from Optimizer into actionable, prioritized, confidence-scored recommendations. It operates as a read-only compute module with optional Chronicle-backed lifecycle tracking. Oracle consumes hypotheses (never measurements), never executes actions, and degrades gracefully when upstream modules are unavailable.

## Output Contract

All recommendations conform to the `Recommendation` model:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier (UUID) |
| `title` | `str` | Short actionable title |
| `description` | `str` | Detailed explanation of the recommendation |
| `priority` | `"critical" \| "high" \| "medium" \| "low"` | Urgency level |
| `confidence` | `float` (0.0–1.0) | Confidence score |
| `evidence` | `dict` | Supporting data from hypotheses |
| `justification` | `str` | Why this recommendation exists |
| `dependencies` | `list[str]` | Module/service preconditions |
| `expiration` | `str` (ISO 8601) | When this recommendation becomes stale |
| `source_hypotheses` | `list[str]` | IDs of source `OptimizationHypothesis`(es) |
| `domain` | `"cost" \| "time" \| "rework" \| "model_efficiency" \| "session_behavior" \| "general"` | Categorization domain |
| `status` | `"active" \| "accepted" \| "rejected" \| "expired"` | Lifecycle state |
| `created_at` | `str` (ISO 8601) | Creation timestamp |

## Requirements

### R1: Recommendation Generation

Oracle MUST generate actionable `Recommendation` objects from `optimizer.hypotheses`. Each Recommendation SHALL be derived from one or more `OptimizationHypothesis` objects by mapping type/domain/confidence to appropriate recommendation fields.

#### Scenario: Full hypothesis input produces recommendations

- GIVEN Optimizer returns a non-empty list of `OptimizationHypothesis` with various types and domains
- WHEN Oracle generates recommendations
- THEN Oracle SHALL return a non-empty `list[Recommendation]`
- AND each `Recommendation` SHALL have all Output Contract fields populated

#### Scenario: Empty hypothesis input

- GIVEN Optimizer returns an empty list
- WHEN Oracle generates recommendations
- THEN Oracle SHALL return an empty list
- AND Oracle SHALL NOT raise errors

#### Scenario: Incomplete hypothesis fields

- GIVEN `OptimizationHypothesis` objects where some have `confidence: 0.0` or missing evidence
- WHEN Oracle generates recommendations
- THEN Oracle SHALL still produce valid `Recommendation` objects with appropriate degraded priority/confidence
- AND `evidence` SHALL indicate partial source data

#### Scenario: Determinism

- GIVEN an identical list of `OptimizationHypothesis` objects
- WHEN Oracle generates recommendations twice
- THEN both runs SHALL produce identical recommendation sets

#### Scenario: Optimizer absent

- GIVEN no `optimizer.hypotheses` service is registered
- WHEN Oracle is queried for recommendations
- THEN Oracle SHALL return an empty list
- AND Oracle SHALL NOT crash

---

### R2: Prioritization

Oracle MUST sort recommendations deterministically by priority (critical > high > medium > low) then by confidence descending. Same input SHALL always produce the same order.

#### Scenario: Mixed priorities sorted correctly

- GIVEN recommendations with all four priority levels
- WHEN Oracle sorts them
- THEN critical SHALL appear first, followed by high, medium, and low
- AND within each priority level, recommendations SHALL be ordered by confidence descending

#### Scenario: Empty input

- GIVEN no recommendations exist
- WHEN Oracle sorts them
- THEN Oracle SHALL return an empty list

#### Scenario: Tied priority and confidence

- GIVEN two recommendations with the same priority and same confidence
- WHEN Oracle sorts them
- THEN the tiebreaker SHALL be deterministic (by `id` or `created_at`)
- AND the order SHALL be consistent across calls

#### Scenario: Determinism

- GIVEN an identical list of recommendations with varying priorities and confidences
- WHEN Oracle sorts them twice
- THEN both results SHALL have identical ordering

#### Scenario: Chronicle absent

- GIVEN Chronicle is unavailable and recommendations are ephemeral
- WHEN Oracle returns sorted recommendations
- THEN the sort order SHALL be identical to the Chronicle-backed mode for the same input

---

### R3: Evidence Preservation

Every `Recommendation` MUST maintain traceability to its source hypotheses. The `source_hypotheses` field SHALL contain the IDs of the `OptimizationHypothesis`(es) that generated it.

#### Scenario: Single-source recommendation

- GIVEN a single `OptimizationHypothesis` drives a recommendation
- WHEN the recommendation is generated
- THEN `source_hypotheses` SHALL contain exactly that hypothesis's ID
- AND `evidence` SHALL contain the hypothesis's original evidence

#### Scenario: Empty hypothesis input

- GIVEN no hypotheses
- WHEN no recommendations are generated
- THEN traceability is trivially satisfied — zero recommendations, zero source references

#### Scenario: Multi-source aggregation

- GIVEN multiple `OptimizationHypothesis` objects from different detectors converge on the same recommendation
- WHEN the recommendation is generated
- THEN `source_hypotheses` SHALL contain all contributing hypothesis IDs
- AND `evidence` SHALL merge evidence from all sources

#### Scenario: Determinism

- GIVEN identical hypothesis sets
- WHEN recommendations are generated twice
- THEN both runs SHALL produce identical `source_hypotheses` for each recommendation

#### Scenario: Chronicle absent

- GIVEN Chronicle is unavailable
- WHEN recommendations are generated
- THEN `source_hypotheses` SHALL still be populated from the current input
- AND traceability SHALL be preserved in memory

---

### R4: Recommendation Lifecycle

Oracle MUST track recommendation lifecycle states: `active`, `accepted`, `rejected`, `expired`. Creation SHALL set `active`. Expiration SHALL be enforced by configurable domain-level TTL. State tracking SHALL be advisory — Oracle tracks, never executes transitions.

#### Scenario: Recommendation created with active state

- GIVEN a recommendation is generated from a hypothesis
- WHEN the recommendation is created
- THEN `status` SHALL be `"active"`
- AND `expiration` SHALL be set based on the default TTL for the recommendation's domain

#### Scenario: Empty input

- GIVEN no hypotheses
- WHEN no recommendations exist
- THEN lifecycle tracking has no items to manage — Oracle SHALL remain stable

#### Scenario: Recommendation expiration

- GIVEN a recommendation whose `expiration` timestamp is in the past
- WHEN Oracle computes recommendations
- THEN the expired recommendation SHALL have `status: "expired"`
- AND Oracle SHALL NOT re-generate expired recommendations from stale hypotheses

#### Scenario: Determinism in lifecycle assignment

- GIVEN identical hypotheses with identical timestamps
- WHEN lifecycle states are assigned twice
- THEN both runs SHALL produce identical status and expiration values

#### Scenario: Chronicle absent

- GIVEN Chronicle is unavailable
- WHEN a recommendation transitions from `active` to `accepted`
- THEN Oracle SHALL record the transition in memory
- AND the transition SHALL NOT be persisted

---

### R5: Chronicle Integration

Oracle MAY persist recommendation lifecycle events via `chronicle.record`. When Chronicle is available, Oracle SHALL write `recommendation_generated`, `recommendation_accepted`, `recommendation_rejected`, and `recommendation_outcome` events. On read, Oracle SHALL reconstruct past state from Chronicle events. When Chronicle is absent, Oracle SHALL operate in ephemeral mode.

#### Scenario: Chronicle available — lifecycle events written

- GIVEN Chronicle is registered and `chronicle.record` is available
- WHEN Oracle creates or transitions a recommendation
- THEN Oracle SHALL write the corresponding event type to Chronicle
- AND the event payload SHALL contain the full `Recommendation` fields

#### Scenario: Chronicle unavailable — ephemeral mode

- GIVEN Chronicle is not registered
- WHEN Oracle generates recommendations
- THEN Oracle SHALL return valid recommendations
- AND Oracle SHALL NOT error or degrade output quality

#### Scenario: Partial Chronicle failures

- GIVEN Chronicle is registered but `chronicle.record` fails intermittently
- WHEN Oracle attempts to write a lifecycle event
- THEN Oracle SHALL log the failure
- AND Oracle SHALL still return recommendations (non-blocking write)

#### Scenario: Determinism in Chronicle writes

- GIVEN identical recommendations being generated
- WHEN Chronicle events are written on two separate runs
- THEN both runs SHALL write semantically identical event payloads

#### Scenario: Read-side reconstruction from Chronicle

- GIVEN past recommendation events exist in Chronicle
- WHEN Oracle reads them back
- THEN Oracle SHALL reconstruct the past recommendation state from the event stream

---

### R6: Optimizer Dependency

Oracle MUST consume ONLY `optimizer.hypotheses` as primary input. Oracle SHALL NEVER read `pulse.measurements` directly. When Optimizer is absent, Oracle SHALL return an empty list.

#### Scenario: Optimizer provides hypotheses

- GIVEN Optimizer is registered and returns hypotheses
- WHEN Oracle generates recommendations
- THEN Oracle SHALL use `optimizer.hypotheses` as the sole source of findings

#### Scenario: Optimizer absent

- GIVEN no `optimizer.hypotheses` service is registered
- WHEN Oracle is called
- THEN Oracle SHALL return an empty list
- AND Oracle SHALL NOT attempt to read Pulse measurements

#### Scenario: Optimizer returns partial results

- GIVEN Optimizer returns hypotheses with missing or malformed fields
- WHEN Oracle processes them
- THEN Oracle SHALL handle each hypothesis individually, producing recommendations for valid ones
- AND Oracle SHALL NOT propagate errors from malformed hypotheses

#### Scenario: Determinism

- GIVEN the same `optimizer.hypotheses` output on two calls
- WHEN Oracle generates recommendations
- THEN both calls SHALL produce identical results

#### Scenario: Pulse is never accessed

- GIVEN Pulse measurements are available in the context
- WHEN Oracle generates recommendations
- THEN Oracle SHALL NOT call `pulse.measurements` or any Pulse service
- AND this SHALL be verifiable through the service registry

---

### R7: Guardian/Vision Enrichment

Oracle MAY degrade recommendation confidence based on Guardian diagnostics or Vision `module_state`. When Guardian reports module failures, confidence of dependent recommendations SHOULD be lowered proportionally. No hard dependency — Oracle functions without Guardian.

#### Scenario: Healthy modules — full confidence

- GIVEN Guardian diagnostics report all modules healthy
- WHEN Oracle computes recommendation confidence
- THEN the base confidence from hypotheses SHALL NOT be degraded

#### Scenario: Guardian absent — no degradation

- GIVEN Guardian is not installed or not registered
- WHEN Oracle computes recommendation confidence
- THEN Oracle SHALL use hypothesis confidence as-is
- AND Oracle SHALL NOT raise errors

#### Scenario: Failing module degrades confidence

- GIVEN Guardian diagnostics report a module (e.g., Pulse) is FAILED
- WHEN Oracle computes confidence for recommendations depending on that module
- THEN the recommendation confidence SHALL be lowered proportionally to the module health
- AND `evidence` SHALL note the degradation source

#### Scenario: Determinism

- GIVEN identical diagnostic states and identical hypotheses
- WHEN confidence is computed twice with Guardian enrichment
- THEN both runs SHALL produce identical confidence values

#### Scenario: Chronicle absent

- GIVEN Chronicle unavailable but Guardian available
- WHEN Oracle degrades confidence based on Guardian state
- THEN the degradation SHALL still be applied to ephemeral recommendations

---

### R8: Standalone Operation

Oracle MUST operate correctly when external services (Optimizer, Chronicle, Guardian, Vision) are absent. Empty input SHALL produce an empty list. Oracle SHALL NEVER crash due to missing dependencies.

#### Scenario: All dependencies absent

- GIVEN no modules other than Oracle are registered
- WHEN Oracle is queried
- THEN Oracle SHALL return an empty list
- AND Oracle SHALL NOT raise or propagate errors

#### Scenario: Optimizer returns empty

- GIVEN Optimizer is registered but returns no hypotheses
- WHEN Oracle generates recommendations
- THEN Oracle SHALL return an empty list

#### Scenario: Partial dependencies available

- GIVEN Optimizer returns hypotheses, but Chronicle and Guardian are absent
- WHEN Oracle generates recommendations
- THEN Oracle SHALL return valid recommendations using only hypothesis data
- AND all recommendations SHALL have `status: "active"` with no Chronicle events written

#### Scenario: Determinism

- GIVEN identical hypotheses and identical service availability
- WHEN Oracle runs twice
- THEN both runs SHALL produce identical output

#### Scenario: No side effects from standalone operation

- GIVEN Oracle runs with no other modules
- WHEN Oracle completes a recommendation cycle
- THEN no files, services, or state SHALL be created or modified outside Oracle

---

### R9: Recommendation Purity

Oracle MUST NOT modify any module's configuration, state, or data. Oracle MUST NOT execute actions. Oracle is a read-only consumer with the sole exception of Chronicle event writes (advisory persistence only).

#### Scenario: Module state unchanged

- GIVEN any set of modules (Optimizer, Pulse, Chronicle, Guardian, Vision) are running
- WHEN Oracle generates recommendations
- THEN no module's internal state SHALL be altered
- AND no module's configuration SHALL be read or written

#### Scenario: Empty input — no side effects

- GIVEN no hypotheses
- WHEN Oracle completes a cycle
- THEN no module SHALL be affected by Oracle's operation

#### Scenario: No action execution

- GIVEN recommendations are generated
- WHEN Oracle completes its cycle
- THEN Oracle SHALL NOT have executed any shell command, config change, or MCP mutation

#### Scenario: Determinism from purity

- GIVEN the same input across two Oracle instances
- WHEN both generate recommendations
- THEN both SHALL produce identical results because neither mutates input or external state

#### Scenario: Chronicle absent guarantees purity

- GIVEN Chronicle unavailable
- WHEN Oracle runs
- THEN Oracle SHALL NOT create, seed, or simulate Chronicle data

---

### R10: Determinism

Given identical input (identical list of `OptimizationHypothesis`, identical Guardian diagnostics, identical service availability), Oracle MUST produce identical recommendations with identical priority, confidence, and ordering across every invocation within the same process lifetime.

#### Scenario: Full-cycle determinism

- GIVEN the same set of hypotheses and same service state
- WHEN Oracle runs the full recommendation cycle twice
- THEN every field in every `Recommendation` SHALL be identical across both runs

#### Scenario: Empty input determinism

- GIVEN empty input on two separate calls
- WHEN Oracle generates recommendations
- THEN both calls SHALL produce identical empty results

#### Scenario: Partial data determinism

- GIVEN the same set of incomplete hypotheses on two calls
- WHEN Oracle generates recommendations
- THEN both runs SHALL produce identical recommendations with identical confidence values

#### Scenario: No random or time-dependent state

- GIVEN any set of hypotheses
- WHEN Oracle generates recommendations
- THEN `id` and `created_at` are the only time/random-dependent fields
- AND all other fields SHALL be fully determined by input data

#### Scenario: Chronicle absent determinism

- GIVEN no Chronicle on two separate starts
- WHEN Oracle generates recommendations
- THEN both calls SHALL produce identical results

---

### R11: Data Ownership

Oracle owns the recommendation model and decision logic. Chronicle owns persisted events. Oracle reconstructs recommendation state on-read from Chronicle when available. When Chronicle is absent, recommendations are ephemeral.

#### Scenario: Model ownership — Oracle defines Recommendation structure

- GIVEN Oracle receives hypotheses
- WHEN Oracle generates a `Recommendation`
- THEN the `Recommendation` SHALL conform to the Output Contract with all fields owned by Oracle's model

#### Scenario: Empty input — no state to own

- GIVEN no hypotheses
- WHEN Oracle has no recommendations
- THEN data ownership division is trivially satisfied — no state exists

#### Scenario: On-read reconstruction from Chronicle

- GIVEN Chronicle has past recommendation events
- WHEN Oracle initializes and reads Chronicle
- THEN Oracle SHALL reconstruct its recommendation state from Chronicle events
- AND Oracle SHALL NOT maintain a separate persistent store

#### Scenario: Determinism in reconstruction

- GIVEN identical Chronicle event sets
- WHEN Oracle reconstructs state twice
- THEN both reconstructions SHALL produce identical recommendation state

#### Scenario: Chronicle absent — ephemeral state

- GIVEN Chronicle is unavailable
- WHEN Oracle operates
- THEN recommendations SHALL be ephemeral — computed and returned without persistence
- AND Oracle SHALL NOT attempt to reconstruct past state

---

## Constraints

The following constraints are non-negotiable and apply to all requirements:

| Constraint | Rule |
|------------|------|
| No action execution | Oracle NEVER executes recommendations. Advisory only. |
| No Pulse ingestion | Oracle NEVER reads `pulse.measurements` directly. Only `optimizer.hypotheses`. |
| No hypothesis re-derivation | Oracle consumes Optimizer output as-is. Never re-derives. |
| No config modification | Oracle does not change module or system configuration. |
| No other module mutation | Oracle never writes to Pulse, Optimizer, Guardian, or Vision. |
| Chronicle owns persistence | Oracle writes events via `chronicle.record`. Never owns storage. |
| Oracle owns the model | Recommendation data model and decision logic belong to Oracle. |
| Deterministic output | Same input → same recommendations with same priority and confidence. |
| Graceful degradation | Missing dependencies → empty or degraded output, never crashes. |
