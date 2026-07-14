# Exploration: Pulse — Performance Intelligence Engine

## Current State

The Master Document (§9) defines Pulse as:

> **Pulse ⏳** — Performance benchmarking.

The Engineering Intelligence Layer design (previous change) refined this to:

| Field | Value |
|-------|-------|
| Intelligence dimension | Performance intelligence |
| System responsibility | Measures engineering productivity — cost, time, rework per feature |
| Consumes from | Agent activity |
| Provides to | Optimizer (data) |

---

## 1. What problem does Pulse solve?

AI coding agents operate in session-scoped isolation. An agent does not know:

- How many tokens were consumed to implement a specific feature.
- Whether the current model is more or less expensive than alternatives for the same task.
- How much engineering time was spent on rework vs. new work.
- Whether productivity is improving, declining, or flat across the project lifecycle.

Engineering teams using AI agents currently have **zero visibility into the economics of their AI-assisted development process**. They see output (commits, PRs, features) but cannot answer fundamental business questions about cost, efficiency, and ROI.

Pulse solves this by providing **persistent, cross-session engineering productivity intelligence**.

---

## 2. What exclusive responsibility does Pulse have within the Engineering Intelligence Layer?

Each module has a distinct domain. Pulse's exclusive responsibility is:

> **Measure and analyze the economics of AI-assisted engineering work.**

| Module | Domain | Pulse relationship |
|--------|--------|-------------------|
| Chronicle | Records project history (events, decisions, timeline) | Pulse can consume event data for cost attribution |
| Guardian | Governs project rules and safe execution | Orthogonal — no overlap |
| Vision | Observes runtime state (health, metrics, introspection) | Vision measures *system* health; Pulse measures *engineering* productivity |
| **Pulse** | **Measures engineering productivity** | **Owns this domain exclusively** |
| Optimizer | Detects improvement opportunities (redundancy, structure) | Pulse provides the data; Optimizer acts on it |
| Oracle | Produces architectural recommendations | Pulse provides productivity context for decisions |

Pulse does not compete with any other module. It fills the gap that no module addresses: **the economics of the engineering process itself**.

---

## 3. What should Pulse NOT do?

| Out of scope | Because |
|-------------|---------|
| CPU/memory/network profiling | That is Vision's domain (runtime observability) |
| Event recording or timeline | That is Chronicle's domain (institutional memory) |
| Policy enforcement or violation detection | That is Guardian's domain (governance) |
| Code/context/token optimization | That is Optimizer's domain |
| Architectural recommendations | That is Oracle's domain |
| Replace git/CI metrics | Those exist already; Pulse consumes them, does not duplicate them |
| Measure individual human developer productivity | Pulse measures *agent* productivity, not people |
| Real-time system alerts | That is Vision's domain |

---

## 4. How does Pulse differ from Chronicle, Guardian, Vision, Optimizer, and Oracle?

### Pulse vs. Chronicle

Chronicle records **what happened** (events, timeline, decisions). Pulse measures **how much it cost** (tokens, time, rework). They are complementary: Pulse can use Chronicle's event stream to calculate per-event cost attribution.

### Pulse vs. Guardian

Guardian defines **what is allowed**. Pulse measures **how efficient it was**. They are orthogonal and do not interact directly.

### Pulse vs. Vision

Vision observes **runtime system state** (module health, resource consumption, introspection). Pulse measures **engineering process economics** (cost per feature, time per PR, model efficiency).

Both produce metrics, but at different levels:
- Vision: "How many requests per second is the engine handling?"
- Pulse: "How many tokens did this PR cost? Which model was more efficient?"

### Pulse vs. Optimizer

Optimizer detects **improvement opportunities in project structure** (redundant context, oversized modules, duplicate specs). Pulse provides the **productivity data** that Optimizer needs to prioritize improvements.

Pulse answers "what is happening." Optimizer answers "what to do about it."

### Pulse vs. Oracle

Oracle synthesizes data from all modules into **architectural recommendations**. Pulse provides the **economic dimension** that Oracle needs for cost-aware reasoning.

Without Pulse, Oracle can reason about structure and risk but not about cost and efficiency.

---

## 5. What information does Pulse consume?

| Source | Data | How obtained |
|--------|------|-------------|
| Agent session | Token count per task, model used, task duration | Direct instrumentation |
| Chronicle | Event stream, task boundaries, project milestones | Optional integration (duck-typed service) |
| Version control | PR metadata, commit size, time-to-merge, rework cycles | Git integration |
| Configuration | Token pricing per model, cost thresholds | Configuration |

Pulse SHOULD function with direct instrumentation alone (no mandatory dependencies on other modules). Integration with Chronicle is OPTIONAL for richer data.

---

## 6. What intelligence does Pulse produce?

| Intelligence | Description | Example |
|-------------|-------------|---------|
| Cost per feature | Total tokens × model rate for a defined task | "PR3 cost $0.42 with GPT-4" |
| Time per PR | Wall-clock time from first commit to merge | "PR4 took 3h 12m" |
| Efficiency ratio | Output quality rating / cost | "Module X: efficiency 8.2/10" |
| Model comparison | Cost and time per model per task type | "Claude-4 was 30% cheaper than GPT-4 for refactoring" |
| Rework percentage | Lines rewritten after initial implementation | "15% of output was modified within 7 days" |
| Trend analysis | Productivity trajectory over time | "Cost per feature decreased 20% over last 5 PRs" |
| Cost attribution | Which area consumed the most resources | "Vision module: 40% of total token spend" |

---

## 7. What decisions does Pulse enable?

| Decision | Question Pulse answers | Impact |
|----------|----------------------|--------|
| Model selection | Which model gives the best cost/quality ratio for this task type? | Reduces token spend by routing tasks to optimal models |
| Task scoping | Should this PR be split? The cost curve shows diminishing returns after N lines. | Improves review efficiency and reduces rework |
| Process improvement | Where are we wasting tokens? (e.g., repeated context loading) | Identifies engineering process bottlenecks |
| Tool evaluation | Is this agent/tool combination cost-effective for this project? | Data-driven tooling decisions |
| Capacity planning | What is the expected cost for the next phase based on historical data? | Budget forecasting |
| ROI analysis | Did the time saved justify the token cost? | Validates AI-assisted development investment |

---

## 8. How does Pulse provide value that a coding agent alone cannot maintain persistently?

A coding agent's context is ephemeral:

| Capability | Agent alone | With Pulse |
|-----------|-------------|------------|
| Remember token cost of previous PRs | ❌ Session-limited | ✅ Persistent store |
| Compare models across tasks | ❌ No cross-session memory | ✅ Accumulated benchmarks |
| Track productivity trends | ❌ No historical data | ✅ Trend analysis |
| Attribute costs to specific features | ❌ No project-level tracking | ✅ Cost breakdown |
| Detect rework patterns | ❌ No long-term diff analysis | ✅ Rework percentage |
| Forecast cost of upcoming work | ❌ No baseline | ✅ Historical basis |

Pulse provides **persistent, cross-session engineering productivity intelligence** that accumlates across the entire project lifecycle — something a coding agent's context window fundamentally cannot provide.

---

## Boundaries Summary

```
Pulse WILL:
├── Measure token consumption per task/PR/feature
├── Track time investment per engineering unit
├── Compare model cost and efficiency
├── Calculate rework percentages
├── Provide trend data over time
└── Feed productivity data to Optimizer and Oracle

Pulse WILL NOT:
├── Profile system performance (Vision)
├── Record event history (Chronicle)
├── Enforce policies (Guardian)
├── Optimize code structure (Optimizer)
├── Produce recommendations (Oracle)
├── Replace existing CI/git metrics
└── Measure human developer productivity
```

---

## Measurement Boundaries

### Metrics Pulse Owns Exclusively

| Metric | Rationale |
|--------|-----------|
| Token consumption per task/PR/feature | No other module measures engineering resource consumption |
| Monetary cost per engineering unit (tokens × model rate) | Derived from token data — Pulse's exclusive calculation |
| Wall-clock time per task/PR/session | Measures engineering process duration, not system uptime |
| Model identifier per task | Attribution of output to specific model for comparison |
| Efficiency ratio (output value / cost) | Composite metric across Pulse's own data |
| Rework percentage (lines modified within N days) | Derived from diff analysis over time |
| Productivity trend (cost/feature over project timeline) | Aggregation of Pulse's own historical data |

### Metrics That Belong to Vision — Explicitly NOT Pulse

| Metric | Owner | Why not Pulse |
|--------|-------|---------------|
| CPU / memory / disk usage | Vision | System resource monitoring, not engineering productivity |
| Module health status (up/down/degraded) | Vision | Runtime observability, not process economics |
| Request latency / throughput | Vision | Performance observability, not cost analysis |
| Ring buffer state / log rotation | Vision | Infrastructure observability |
| Process uptime / PID | Vision | System lifecycle, not engineering process |

### Data Pulse Collects but Optimizer Interprets

Pulse acts as a **data provider** for Optimizer. It stores raw measurements that Optimizer consumes to detect improvement opportunities:

| Pulse measurement | Optimizer uses it to... |
|------------------|------------------------|
| Token cost per module | Detect which module has disproportionate resource consumption |
| Time per PR | Recommend PR splitting when time/cost curve shows diminishing returns |
| Rework percentage | Flag modules or patterns with high rework (candidates for redesign) |
| Model efficiency per task type | Recommend task-to-model routing changes |

Pulse does NOT interpret these measurements — it only collects, stores, and provides them. Interpretation is Optimizer's responsibility.

### Data Pulse Collects but Oracle Uses as Context

Oracle consumes Pulse data as one input among several (Chronicle, Guardian, Vision, Optimizer) to produce architectural recommendations:

| Pulse measurement | Oracle uses it to... |
|------------------|---------------------|
| Historical cost per feature | Include economic impact in architectural recommendations |
| Productivity trends over time | Assess whether architectural changes improved or degraded productivity |
| Rework patterns by module | Factor maintenance cost into architecture risk analysis |

Pulse does NOT make recommendations — it only provides the economic data layer. Recommendations are Oracle's responsibility.

### Metrics Pulse Will NEVER Store

| Metric | Reason |
|--------|--------|
| Session content (prompts, responses, code) | Privacy / scope — Pulse measures cost, not content |
| Developer identity or personal metrics | Pulse measures *agent* productivity, not people |
| System performance metrics (CPU, memory, etc.) | Owned by Vision |
| Event history or decisions | Owned by Chronicle |
| Policy violations or rule breaches | Owned by Guardian |
| Code structure or dependency analysis | Owned by Optimizer |
| Architectural recommendations or risk scores | Owned by Oracle |
| Git commit content or diffs | Pulse stores only *metadata* (size, time, rework count), not content |

---

## Data Ownership: No Overlap

Every data type has exactly one module as its authoritative owner:

| Data type | Owner | Consumed by |
|-----------|-------|-------------|
| Event history (what happened) | Chronicle | Oracle, Pulse (optional) |
| Decisions and rationale | Chronicle | Oracle |
| Timeline and milestones | Chronicle | Oracle, Pulse |
| Policy definitions | Guardian | Guardian itself |
| Rule violations | Guardian | Oracle |
| Execution diagnostics | Guardian | Vision, Oracle |
| Module health status | Vision | Guardian, Oracle |
| Runtime metrics (CPU, memory, latency) | Vision | Guardian, Optimizer |
| System introspection data | Vision | Operator |
| **Token consumption** | **Pulse** | Optimizer, Oracle |
| **Monetary cost per task** | **Pulse** | Optimizer, Oracle |
| **Time per PR/session** | **Pulse** | Optimizer, Oracle |
| **Model efficiency comparison** | **Pulse** | Optimizer, Oracle |
| **Rework percentage** | **Pulse** | Optimizer, Oracle |
| **Productivity trends** | **Pulse** | Oracle |
| Redundancy analysis | Optimizer | Oracle |
| Improvement recommendations | Optimizer | Oracle |
| Architectural recommendations | Oracle | Developer |
| Risk analysis | Oracle | Developer |

**Key rule for implementation**: No module may write data that another module owns. Pulse writes token counts, time, cost, rework — and nothing else. If another module needs Pulse data, it reads from Pulse's store; it does not duplicate it.

---

## Ready for Proposal

**Yes**. The conceptual analysis establishes Pulse's identity within the Engineering Intelligence Layer: it is the **productivity economics engine** that measures what agents cannot measure about themselves. It has clear boundaries against all other modules, a well-defined data flow, and produces intelligence that enables concrete engineering decisions.

No APIs, classes, CLI, or implementation details have been specified. No architecture has been assumed. No roadmap has been modified.
