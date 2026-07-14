# Optimizer — Engineering Optimization Intelligence Specification

## Purpose

Optimizer detects patterns, anomalies, and opportunities for improvement in engineering workflows. It produces structured, confidence-scored `OptimizationHypothesis` objects from available measurement data. Pulse is an optional data source — Optimizer functions standalone with empty data and never prescribes or executes actions.

## Output Contract

All hypotheses conform to `OptimizationHypothesis`:

| Field | Type | Description |
|-------|------|-------------|
| `type` | `pattern \| anomaly \| opportunity` | Classification of the finding |
| `domain` | `cost \| time \| rework \| model_efficiency \| session_behavior` | Domain the hypothesis applies to |
| `confidence` | `float` (0.0–1.0) | Statistical or heuristic confidence |
| `evidence` | `dict` | Supporting data (deltas, baselines, counts, correlations) |
| `affected_scope` | `str` | Description of what the finding affects |
| `generated_at` | `str` (ISO 8601) | Timestamp of hypothesis generation |

## Requirements

### R1: Baseline Generation

Optimizer MUST compute historical baselines from Pulse measurements — mean, standard deviation, minimum, and maximum per metric (tokens_input, tokens_output, cost, wall_clock_s).

#### Scenario: Happy path with full data

- GIVEN three or more WorkUnits with complete measurements
- WHEN Optimizer generates baselines
- THEN mean, std-dev, min, and max SHALL be computed for tokens_input, tokens_output, cost, and wall_clock_s

#### Scenario: Empty dataset

- GIVEN zero WorkUnits
- WHEN baselines are requested
- THEN Optimizer SHALL return an empty baseline set

#### Scenario: Incomplete data

- GIVEN WorkUnits where some have `cost: None` or missing `completed_at`
- WHEN baselines are computed
- THEN Optimizer SHALL skip the missing field for that unit and compute from available data

#### Scenario: Determinism

- GIVEN an identical set of WorkUnits on two separate calls
- WHEN baselines are computed both times
- THEN both results SHALL be bitwise identical

#### Scenario: Pulse unavailable

- GIVEN no `pulse.measurements` service registered
- WHEN baselines are requested
- THEN Optimizer SHALL return an empty baseline set

---

### R2: Degradation Detection

Optimizer MUST detect metric degradations by comparing recent measurements against established baselines.

#### Scenario: Degradation detected

- GIVEN a baseline exists AND a recent measurement exceeds baseline + N×std-dev
- WHEN degradation detection runs
- THEN Optimizer SHALL produce an `OptimizationHypothesis` with `type: anomaly` and `domain: cost` (or relevant domain)

#### Scenario: No baseline

- GIVEN no baseline has been computed
- WHEN degradation detection runs
- THEN Optimizer SHALL return no degradation hypotheses

#### Scenario: Incomplete recent data

- GIVEN a recent WorkUnit missing cost or tokens data
- WHEN degradation detection evaluates it
- THEN Optimizer SHALL skip the missing metric and evaluate only available metrics

#### Scenario: Determinism

- GIVEN identical baseline and identical measurements
- WHEN degradation detection runs twice
- THEN both runs SHALL produce identical hypotheses with identical confidence

#### Scenario: Pulse unavailable

- GIVEN no Pulse data
- WHEN degradation detection runs
- THEN Optimizer SHALL return no degradation hypotheses

---

### R3: Model Efficiency Analysis

Optimizer MUST compare model efficiency metrics (cost per token, time per work unit) across models present in measurements.

#### Scenario: Multiple models compared

- GIVEN WorkUnits from two or more distinct models
- WHEN efficiency analysis runs
- THEN Optimizer SHALL produce hypotheses with `domain: model_efficiency` comparing cost-per-token and time-per-unit across models

#### Scenario: Single model only

- GIVEN WorkUnits from only one model
- WHEN efficiency analysis runs
- THEN Optimizer SHALL return no efficiency hypotheses

#### Scenario: Model with partial cost data

- GIVEN a model where some WorkUnits lack cost attribution
- WHEN efficiency analysis runs
- THEN Optimizer SHALL compute efficiency metrics from units with available cost and note partial coverage in evidence

#### Scenario: Determinism

- GIVEN identical WorkUnits
- WHEN efficiency analysis runs twice
- THEN both runs SHALL produce identical hypotheses

#### Scenario: Pulse unavailable

- GIVEN no Pulse data
- WHEN efficiency analysis runs
- THEN Optimizer SHALL return no efficiency hypotheses

---

### R4: Anomaly Detection

Optimizer MUST identify statistical outliers in measurement distributions using z-score or IQR methods.

#### Scenario: Outlier detected

- GIVEN a distribution of cost or time measurements
- AND one value exceeds the IQR-based or z-score threshold
- WHEN anomaly detection runs
- THEN Optimizer SHALL produce an `OptimizationHypothesis` with `type: anomaly` and evidence containing the outlier and threshold

#### Scenario: No outliers

- GIVEN all measurements fall within expected ranges
- WHEN anomaly detection runs
- THEN Optimizer SHALL return no anomaly hypotheses

#### Scenario: Incomplete distribution

- GIVEN fewer than three measurements for a metric
- WHEN anomaly detection evaluates that metric
- THEN Optimizer SHALL return no anomaly hypotheses for that metric

#### Scenario: Determinism

- GIVEN identical measurement sets
- WHEN anomaly detection runs twice
- THEN both runs SHALL flag the same outliers with identical confidence

#### Scenario: Pulse unavailable

- GIVEN no Pulse data
- WHEN anomaly detection runs
- THEN Optimizer SHALL return no anomaly hypotheses

---

### R5: Session Pattern Analysis

Optimizer MUST detect temporal patterns in session data — time-of-day clustering, session duration trends, and frequency changes.

#### Scenario: Temporal pattern detected

- GIVEN multiple WorkUnits with timestamps spanning a significant period
- WHEN session pattern analysis runs
- THEN Optimizer SHALL produce hypotheses with `domain: session_behavior` for any detected cluster or trend

#### Scenario: Insufficient session data

- GIVEN fewer than three WorkUnits
- WHEN session pattern analysis runs
- THEN Optimizer SHALL return no session pattern hypotheses

#### Scenario: Missing timestamps

- GIVEN WorkUnits where some have empty `created_at`
- WHEN session pattern analysis runs
- THEN Optimizer SHALL exclude units without timestamps from temporal analysis

#### Scenario: Determinism

- GIVEN identical WorkUnits with identical timestamps
- WHEN session pattern analysis runs twice
- THEN both runs SHALL produce identical pattern hypotheses

#### Scenario: Pulse unavailable

- GIVEN no Pulse data
- WHEN session pattern analysis runs
- THEN Optimizer SHALL return no pattern hypotheses

---

### R6: Rework Correlation

Optimizer MUST correlate conditions (model, session duration, time of day) with rework metrics.

#### Scenario: Correlation detected

- GIVEN WorkUnits with measurable rework AND a common condition among high-rework units
- WHEN rework correlation runs
- THEN Optimizer SHALL produce an `OptimizationHypothesis` with `domain: rework` describing the correlation

#### Scenario: No rework data

- GIVEN no WorkUnits with rework metrics available
- WHEN rework correlation runs
- THEN Optimizer SHALL return no correlation hypotheses

#### Scenario: Partial condition data

- GIVEN rework data exists but some condition fields are absent
- WHEN rework correlation runs
- THEN Optimizer SHALL correlate on available conditions and note missing fields in evidence

#### Scenario: Determinism

- GIVEN identical WorkUnits
- WHEN rework correlation runs twice
- THEN both runs SHALL produce identical correlation hypotheses

#### Scenario: Pulse unavailable

- GIVEN no Pulse data
- WHEN rework correlation runs
- THEN Optimizer SHALL return no correlation hypotheses

---

### R7: Hypothesis Generation

All internal detectors MUST produce output exclusively as `OptimizationHypothesis` objects conforming to the Output Contract.

#### Scenario: Valid hypothesis produced

- GIVEN any internal detector identifies a finding
- WHEN a hypothesis is generated
- THEN it SHALL contain `type`, `domain`, `confidence`, `evidence`, `affected_scope`, and `generated_at` per the Output Contract
- AND `generated_at` SHALL be the current wall-clock time in ISO 8601 format

#### Scenario: Empty input yields no hypotheses

- GIVEN no measurements available
- WHEN hypothesis generation runs through all detectors
- THEN the result SHALL be an empty list

#### Scenario: Detector with partial evidence

- GIVEN a detector that found a signal from incomplete data
- WHEN a hypothesis is generated
- THEN the `evidence` field SHALL indicate which fields were partial or missing

#### Scenario: Determinism

- GIVEN identical input across all detectors
- WHEN hypothesis generation runs twice
- THEN both runs SHALL produce identical hypothesis lists

#### Scenario: Pulse unavailable

- GIVEN no Pulse service
- WHEN all detectors run
- THEN they SHALL collectively produce an empty hypothesis list

---

### R8: Confidence Scoring

Every `OptimizationHypothesis` MUST include a `confidence` field with a value between 0.0 and 1.0, representing the certainty of the finding.

#### Scenario: Confidence from evidence strength

- GIVEN a finding with strong evidence (multiple data points, high effect size)
- WHEN the confidence is scored
- THEN `confidence` SHALL be proportionally higher than for weak-evidence findings

#### Scenario: Low-data confidence floor

- GIVEN a finding based on minimal data (e.g., two data points)
- WHEN the confidence is scored
- THEN `confidence` SHALL NOT exceed 0.5 for statistically underpowered findings

#### Scenario: Partial data reduces confidence

- GIVEN a finding where some evidence fields are derived from partial data
- WHEN the confidence is scored
- THEN the `evidence` field SHALL indicate partial coverage
- AND `confidence` MAY be reduced proportionally

#### Scenario: Determinism

- GIVEN identical evidence for two separate hypothesis generation runs
- WHEN confidence is scored both times
- THEN both scores SHALL be identical

#### Scenario: Pulse unavailable (no scoring needed)

- GIVEN no hypotheses generated (empty result)
- WHEN confidence scoring has no input
- THEN Optimizer SHALL remain stable — no scoring attempted

---

### R9: Standalone Operation

Optimizer MUST function correctly with no input data, no Pulse service, and no dependencies on other Engineering Intelligence modules.

#### Scenario: Module starts without Pulse

- GIVEN Pulse is not installed or not registered
- WHEN Optimizer starts and runs `optimizer.hypotheses`
- THEN Optimizer SHALL return an empty hypothesis list
- AND Optimizer SHALL NOT raise or propagate errors

#### Scenario: Empty dataset yields empty results

- GIVEN no measurements are available from any source
- WHEN any detector runs
- THEN it SHALL return no hypotheses

#### Scenario: Pulse becomes unavailable mid-operation

- GIVEN Optimizer previously had Pulse data
- WHEN Pulse is removed from `context.services`
- THEN Optimizer SHALL degrade gracefully and return empty results without crashing

#### Scenario: Determinism with no dependencies

- GIVEN no modules other than Optimizer are active
- WHEN `optimizer.hypotheses` is called twice
- THEN both calls SHALL return identical (empty) results

#### Scenario: No side effects from standalone operation

- GIVEN Optimizer runs with no Pulse
- WHEN it completes a hypothesis cycle
- THEN no files, services, or state SHALL be created or modified outside the Optimizer module

---

### R10: Data Purity

Optimizer MUST NOT modify, delete, or persist any measurement data it reads. All analysis is read-only.

#### Scenario: Input unchanged after analysis

- GIVEN a list of WorkUnits consumed by a detector
- WHEN the detector completes
- THEN the original WorkUnit objects SHALL be identical to their state before the detector ran

#### Scenario: No persistence during analysis

- GIVEN Optimizer completes a full hypothesis cycle
- WHEN inspected
- THEN Optimizer SHALL NOT have written any files, database records, or persistent state

#### Scenario: No modification of Pulse state

- GIVEN Optimizer reads Pulse data via `pulse.measurements`
- WHEN hypotheses are generated
- THEN Optimizer SHALL NOT call any Pulse method that mutates Pulse's own state

#### Scenario: Determinism from immutability

- GIVEN the same input data is provided to two separate Optimizer instances
- WHEN both complete a hypothesis cycle
- THEN both SHALL produce identical results because neither mutated the input

#### Scenario: Pulse unavailable guarantees purity

- GIVEN no Pulse service exists
- WHEN Optimizer runs
- THEN Optimizer SHALL NOT attempt to create, seed, or simulate Pulse data

---

### R11: Oracle Integration

Optimizer MUST expose hypotheses via three duck-typed services: `optimizer.hypotheses`, `optimizer.baselines`, and `optimizer.status`.

#### Scenario: Services return hypotheses

- GIVEN Optimizer is running with detected findings
- WHEN `context.services.get("optimizer.hypotheses")` is called
- THEN it SHALL return `list[OptimizationHypothesis]` (non-empty when findings exist)

#### Scenario: Empty services when no data

- GIVEN Optimizer has no measurements
- WHEN `optimizer.hypotheses` or `optimizer.baselines` are called
- THEN both SHALL return empty lists

#### Scenario: Status reflects availability

- GIVEN Optimizer is running
- WHEN `context.services.get("optimizer.status")` is called
- THEN it SHALL return a dict with `available: true`, `hypothesis_count`, `baseline_count`, and `pulse_connected`

#### Scenario: Determinism in service output

- GIVEN identical internal state
- WHEN a service is called twice
- THEN both calls SHALL return identical data

#### Scenario: Pulse absent reflected in status

- GIVEN Pulse is not connected
- WHEN `optimizer.status` is called
- THEN `pulse_connected` SHALL be `false`
- AND `hypothesis_count` SHALL be zero

---

### R12: Determinism

Given identical input, Optimizer MUST produce identical hypotheses with identical confidence levels across every invocation within the same process lifetime.

#### Scenario: Full-cycle determinism

- GIVEN the same set of WorkUnits
- WHEN the full hypothesis cycle runs twice sequentially
- THEN every `OptimizationHypothesis` produced SHALL have identical fields in both runs

#### Scenario: Empty input determinism

- GIVEN empty input on two separate calls
- WHEN the hypothesis cycle runs
- THEN both calls SHALL produce identical empty results

#### Scenario: Partial data determinism

- GIVEN the same set of incomplete WorkUnits
- WHEN the hypothesis cycle runs twice
- THEN both runs SHALL produce identical hypotheses with identical confidence values

#### Scenario: No random or time-dependent state

- GIVEN any set of measurements
- WHEN Optimizer generates hypotheses
- THEN `generated_at` is the only time-dependent field — all other fields SHALL be fully determined by input data

#### Scenario: Pulse absent determinism

- GIVEN no Pulse service on two separate starts
- WHEN `optimizer.hypotheses` is called on each
- THEN both calls SHALL produce identical empty results

---

## Constraints

The following constraints are non-negotiable and apply to all requirements:

| Constraint | Rule |
|------------|------|
| No action recommendations | Optimizer NEVER recommends, prescribes, or suggests specific actions. It only produces hypotheses. |
| No data mutation | Optimizer NEVER modifies, deletes, or transforms measurement data. All analysis is read-only. |
| No persistence | Optimizer NEVER persists derived intelligence (baselines, hypotheses) to disk, database, or any durable store. |
| No execution | Optimizer NEVER executes any optimization or change based on its hypotheses. |
| Hypotheses only | Optimizer's only output is `OptimizationHypothesis` objects returned to callers. |

Optimizer is a detection and intelligence layer. It identifies what is happening — never what to do about it. Interpretation and action belong to downstream consumers (Oracle, operators, automated tooling).
