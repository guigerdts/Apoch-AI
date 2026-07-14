# Pulse — Productivity Intelligence Specification

## Purpose

Pulse is the Engineering Productivity Intelligence module of the Engineering Intelligence Layer. It is responsible for measuring the economics of AI-assisted software engineering across sessions and projects — token consumption, monetary cost, time investment, model efficiency, and rework patterns.

Pulse produces quantitative intelligence. It does not interpret, optimize, recommend, govern, or observe infrastructure. Optimizer interprets Pulse data; Oracle consumes it as economic context for architectural decisions.

Each requirement in this spec traces to one or more acceptance criteria from the approved proposal and has been verified against the five-question strategic filter: it strengthens Pulse's exclusive responsibility, does not duplicate another module, and provides persistent intelligence that a coding agent cannot maintain alone.

---

## Requirements

### R1: Token Measurement

Pulse MUST measure token consumption per identifiable work unit.

A work unit is the smallest meaningful engineering output that can be attributed — a task, a PR, or a feature boundary.

#### Scenario: Token count recorded per work unit

- GIVEN a work unit with a defined start and end boundary
- WHEN Pulse receives the session data for that work unit
- THEN the total token count consumed during the work unit SHALL be recorded
- AND the measurement SHALL be attributable to that specific work unit

#### Scenario: Incomplete work unit does not produce a measurement

- GIVEN a work unit that started but has no end boundary
- WHEN Pulse evaluates the session data
- THEN Pulse SHOULD NOT record a measurement for that incomplete work unit
- AND Pulse MAY retain partial data if the work unit resumes later

---

### R2: Cost Attribution

Pulse MUST attribute monetary cost to each measured work unit using configurable model pricing.

#### Scenario: Cost calculated from token count and model rate

- GIVEN a work unit with recorded token consumption and a known model identifier
- WHEN the cost attribution runs
- THEN the monetary cost SHALL be calculated as token count × configured price per token for that model
- AND the cost SHALL be stored alongside the work unit

#### Scenario: Unknown model price produces no cost

- GIVEN a work unit with a model identifier that has no configured price
- WHEN cost attribution runs
- THEN Pulse MUST NOT calculate a cost
- AND Pulse SHOULD report the missing price configuration

---

### R3: Time Measurement

Pulse MUST measure wall-clock time per work unit.

#### Scenario: Duration recorded from start to end

- GIVEN a work unit with start and end timestamps
- WHEN Pulse processes the time data
- THEN the wall-clock duration SHALL be recorded
- AND it SHALL be attributable to the work unit

---

### R4: Model Attribution

Pulse MUST record which model was used for each work unit.

#### Scenario: Model identifier captured

- GIVEN a work unit executed under a known model
- WHEN Pulse receives the session metadata
- THEN the model identifier SHALL be recorded alongside the work unit's measurements

#### Scenario: Unknown model reported

- GIVEN a work unit with no identifiable model
- WHEN Pulse processes the session data
- THEN Pulse SHALL record the model as "unknown"
- AND Pulse SHOULD surface the missing attribution

---

### R5: Rework Analysis

Pulse MUST calculate rework percentage for code output within a configurable time window.

Rework is defined as lines modified within N days after initial implementation, where N is configurable.

#### Scenario: Rework percentage calculated

- GIVEN an initial implementation with known line count
- AND subsequent modifications within the configured rework window
- WHEN Pulse analyzes the diff metadata
- THEN the rework percentage SHALL be calculated as (modified lines ÷ original lines) × 100
- AND it SHALL be attributable to the original work unit

#### Scenario: No rework

- GIVEN an initial implementation with no modifications within the rework window
- WHEN Pulse evaluates the same time window
- THEN the rework percentage SHALL be zero for that work unit

---

### R6: Trend Data

Pulse MUST provide productivity trend data over the project timeline.

#### Scenario: Trend available from multiple work units

- GIVEN two or more completed work units with recorded measurements
- WHEN Pulse aggregates the data
- THEN a trend view SHALL be available showing cost and time per work unit over time

#### Scenario: Single work unit produces no trend

- GIVEN only one completed work unit
- WHEN trend data is requested
- THEN Pulse SHOULD indicate insufficient data for a trend
- AND SHOULD include the single data point for reference

---

### R7: Optimizer Integration

Pulse MUST expose its measurements for consumption by the Optimizer module.

#### Scenario: Optimizer reads Pulse data

- GIVEN Pulse has recorded measurements for one or more work units
- WHEN Optimizer requests productivity data
- THEN Optimizer SHALL receive token counts, cost, time, model, and rework data
- AND Pulse MUST NOT interpret or filter the data — it provides raw measurements

---

### R8: Oracle Integration

Pulse MUST expose its measurements for consumption by the Oracle module.

#### Scenario: Oracle reads Pulse data

- GIVEN Pulse has recorded measurements over time
- WHEN Oracle requests economic context
- THEN Oracle SHALL receive historical cost and trend data
- AND Pulse MUST NOT filter or summarize beyond what Oracle requests

---

### R9: Data Privacy

Pulse MUST NOT store session content, developer identity, or system performance metrics.

#### Scenario: Session content excluded

- GIVEN a session with prompts, responses, and code output
- WHEN Pulse records measurements
- THEN Pulse MUST NOT store any prompt text, response text, or code content
- AND Pulse MUST only store the token count, model, time, and cost derived from that session

#### Scenario: No people metrics

- GIVEN a work unit attributed to a developer
- WHEN Pulse processes the session
- THEN Pulse MUST NOT store developer name, email, or any personally identifiable information

#### Scenario: No system metrics

- GIVEN runtime system data (CPU, memory, latency) alongside session data
- WHEN Pulse processes the session
- THEN Pulse MUST NOT store any system performance metrics

---

### R10: Cross-Session Persistence

Pulse MUST preserve all measurements across session boundaries.

#### Scenario: Measurement survives between sessions

- GIVEN a work unit measured in Session A
- WHEN Session B starts and Pulse loads its data
- THEN the measurement from Session A SHALL be available in Session B
- AND all accumulated measurements SHALL remain available across subsequent sessions

#### Scenario: Data survives deployment

- GIVEN Pulse has collected measurements over multiple sessions
- WHEN Pulse is restarted or updated
- THEN all prior measurements SHALL be recoverable

---

### R11: Measurement Independence

Pulse MUST fulfill its core measurement responsibilities without requiring any other Engineering Intelligence Layer module.

Integrations with Chronicle, Vision, Guardian, Optimizer, or Oracle are optional enhancements — never prerequisites for Pulse to function.

#### Scenario: Standalone operation

- GIVEN no Engineering Intelligence Layer modules are available
- WHEN Pulse receives session data
- THEN Pulse SHALL collect tokens, cost, time, model, and rework for each work unit
- AND Pulse SHALL preserve those measurements for future cross-session access

#### Scenario: Optional module integration

- GIVEN one or more Engineering Intelligence Layer modules are available (e.g. Chronicle for enriched attribution)
- WHEN Pulse operates
- THEN Pulse SHOULD use the available module to enhance its measurements where applicable
- BUT Pulse MUST still function if that module becomes unavailable

#### Scenario: Module becomes unavailable mid-operation

- GIVEN Pulse is operating with an available module (e.g. Optimizer)
- WHEN that module becomes unavailable
- THEN Pulse MUST continue collecting and preserving its own measurements
- AND Pulse MUST NOT enter a degraded state for its core responsibilities
