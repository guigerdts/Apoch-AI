# Apoch-AI MCP Public API

> Version 1.0 — PR10 (PR8: core tools, PR9: legacy aliases)

## Table of Contents

1. [Introduction](#introduction)
2. [Response Format](#response-format)
   - [Success: ToolResponse](#success-toolresponse)
   - [EvidenceSource](#evidencesource)
   - [RecommendResponse](#recommendresponse)
   - [Error: ErrorResponse](#error-errorresponse)
3. [The 7 Tools](#the-7-tools)
   - [apoch_status](#1-apoch_status)
   - [apoch_health](#2-apoch_health)
   - [apoch_history](#3-apoch_history)
   - [apoch_recommend](#4-apoch_recommend)
   - [apoch_progress](#5-apoch_progress)
   - [apoch_insights](#6-apoch_insights)
   - [apoch_logs](#7-apoch_logs)
4. [Legacy Aliases](#legacy-aliases)
5. [Migration Guide](#migration-guide)
6. [Error Catalog](#error-catalog)
7. [API Reference](#api-reference)
8. [FAQ](#faq)
9. [Best Practices](#best-practices)
10. [Changelog](#changelog)

---

## Introduction

Apoch-AI exposes a **Model Context Protocol (MCP) API** — a set of tools that an AI agent (such as an LLM or an automation system) can call to inspect, diagnose, and understand the Apoch-AI runtime.

The API gives agents access to seven capabilities:

| Tool | What you get |
|---|---|
| `apoch_status` | One-shot overview of the entire system |
| `apoch_health` | Active problems, severity, and per-issue actions |
| `apoch_history` | Chronological log of lifecycle, tool calls, and errors |
| `apoch_recommend` | The single highest-impact action to take right now |
| `apoch_progress` | Productivity trend — how much work happened over a period |
| `apoch_insights` | Detected patterns and improvement opportunities |
| `apoch_logs` | Raw debug log entries with level and module filters |

Every tool follows the same contract: it returns a **ToolResponse** (success) or an **ErrorResponse** (failure). There are no other return paths.

### How tools reach their answers

Apoch-AI is composed of internal modules (Vision, Guardian, Chronicle, Pulse, Optimizer, Oracle). The `ApochCoordinator` orchestrates these modules — it queries them in parallel with individual timeouts, aggregates their responses, and translates internal data into user-facing answers. Tools never expose module names, internal IDs, or raw data structures.

### Transport

The API is served over stdio MCP transport. The MCP framework wraps successful responses in the standard envelope:

```json
{"version": 1, "ok": true, "data": { ... }}
```

Error responses include the envelope themselves (see [Error: ErrorResponse](#error-errorresponse)).

### API Version

`API_VERSION = "1.0"`

Defined in `src/apoch/public_api/version.py`. Follows MAJOR.MINOR versioning per ADR-005:

- **MAJOR**: breaking changes (removing or renaming required fields)
- **MINOR**: compatible additions (new optional fields, new evidence sources)

The version is returned in every ToolResponse as the `api_version` field.

---

## Response Format

### Success: ToolResponse

Every successful tool call returns a dict with these fields:

```python
@dataclass
class ToolResponse:
    api_version: str        # "1.0"
    summary: str            # One-line answer
    explanation: str        # Brief context (may contain newlines)
    evidence: list          # List of EvidenceSource dicts
    suggested_action: str | None  # Recommended next step, or None
    confidence: float       # 0.00–1.00, global confidence in this answer
    generated_at: str       # ISO 8601 UTC timestamp
    data_freshness: int     # Age of source data in seconds
    metadata: dict          # Extensibility — legacy compat, future fields
```

Defined at `src/apoch/public_api/models.py:55`.

| Field | Always present | Description |
|---|---|---|
| `api_version` | Yes | Version of the API contract that produced this response (`"1.0"`). |
| `summary` | Yes | A single-line human-readable answer. May start with an emoji for status/health. |
| `explanation` | Yes | Context. May contain newlines for structured output (narratives, problem lists, log entries). |
| `evidence` | Yes | Array of `EvidenceSource` dicts. Each represents one module that contributed data. Empty if no modules responded. |
| `suggested_action` | No | An action the caller can take. `null` for pure-query tools (history, progress, insights, logs). |
| `confidence` | Yes | 0.00–1.00. See per-tool docs for how this is computed. |
| `generated_at` | Yes | ISO 8601 with timezone (UTC). |
| `data_freshness` | Yes | 0 = fresh from live query (current implementation always returns 0). |
| `metadata` | Yes | Reserved for future use. Empty `{}` for standard tools; contains `legacy_tool`, `replaced_by`, `deprecated_since` when called through a [legacy alias](#legacy-aliases). |

### EvidenceSource

Each entry in `evidence` is a dict:

```python
@dataclass
class EvidenceSource:
    source: str         # Module name ("Vision") or functional label ("Sistema de recomendaciones") — see note below
    confidence: float   # Reliability of this source (0.00–1.00, currently fixed at 0.8)
    collected_ago: int  # Seconds since collection (currently always 0)
    based_on: str       # What data was used (e.g. "5 events", "38 work units")
```

Evidence sources use two naming conventions depending on the tool:
- **Module names** — `status`, `health`, `history`, `progress`, `insights`, and `logs` use capitalized module names (`"Vision"`, `"Guardian"`, `"Chronicle"`, `"Oracle"`) as evidence sources. This is the default convention — `_build_evidence()` maps each module key to its capitalized name.
- **Functional labels** — `recommend` uses descriptive labels (per architecture constraint P6 — no exposed implementation) such as `"Sistema de recomendaciones"` and `"Diagnóstico del sistema"`, built by `_build_recommend_evidence()`.

### RecommendResponse

`apoch_recommend` extends ToolResponse with two additional fields:

```python
@dataclass
class RecommendResponse(ToolResponse):
    priority: str             # "HIGH" | "MEDIUM" | "LOW"
    expected_benefit: str | None  # Projected impact, or None
```

Defined at `src/apoch/public_api/models.py:121`.

| Field | Always present | Description |
|---|---|---|
| `priority` | Yes | `"HIGH"`, `"MEDIUM"`, or `"LOW"`. Derived from Oracle priority or Guardian severity. |
| `expected_benefit` | No | A description of what will improve if the recommendation is followed. Currently always `null` (reserved for future Oracle integration). |

### Error: ErrorResponse

When a tool cannot produce a valid response, it returns:

```json
{
  "version": 1,
  "ok": false,
  "error": {
    "code": "ERR_...",
    "message": "Human-readable description"
  }
}
```

The outer envelope uses ``\"version\"`` (envelope version, always 1) and ``\"ok\"`` (always ``false``). The error details live under ``\"error\"``. Defined at `src/apoch/adapters/opencode/server.py:_dispatch()`.

| Field | Always present | Description |
|---|---|---|
| `version` | Yes | Envelope version (always 1). |
| `ok` | Yes | Always `false`. |
| `error.code` | Yes | One of the 9 error codes from the [Error Catalog](#error-catalog). |
| `error.message` | Yes | Human-readable explanation, typically in Spanish (the system's default locale). |

---

## The 7 Tools

### 1. apoch_status

**Purpose**: Get a one-shot overview of the entire system — what components are active, whether there are problems, and what happened recently.

**Human question answered**: *"How is the system doing right now?"*

**What it does**:
- Queries Vision (module states) — mandatory
- Queries Guardian (all diagnostics) — mandatory
- Queries Chronicle (events in the last 5 minutes, max 5 events) — mandatory
- Queries Oracle (status recommendation) — optional

All queries run in parallel with individual timeouts (Vision: 1s, Guardian: 0.5s, Chronicle: 0.5s, Oracle: 2s). Modules that time out or fail return `None` and are omitted from evidence.

**What it does NOT do**:
- Does not diagnose specific problems (use `apoch_health`)
- Does not show the full event timeline (use `apoch_history`)
- Does not recommend a next action (use `apoch_recommend`)
- Does not show raw log entries (use `apoch_logs`)

**Parameters**: None.

**Examples**:

<details>
<summary>All systems healthy — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "🟢 Todos los sistemas operativos",
  "explanation": "3 componentes activos — sin errores — actividad reciente disponible",
  "evidence": [
    {"source": "Vision", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Guardian", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Chronicle", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": "Ninguna acción requerida",
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:00:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Problems detected — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "🔴 Sistema operativo con problemas detectados",
  "explanation": "3 componentes activos — problemas detectados — actividad reciente disponible",
  "evidence": [
    {"source": "Vision", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Guardian", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Chronicle", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": "Revise los problemas detectados",
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:00:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Partial response — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "🟡 Sistema funcionando con limitaciones",
  "explanation": "3 componentes activos — sin errores — sin datos de actividad reciente",
  "evidence": [
    {"source": "Vision", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Guardian", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": "Ninguna acción requerida",
  "confidence": 0.67,
  "generated_at": "2026-07-17T12:00:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_TIMEOUT` | No module responded at all (all timed out or failed). |

**Use cases**:
- Dashboard widget showing system health
- First check when debugging — "is the system running?"
- Proactive agent monitoring loop

**Best practices**:
- Call this first when starting a diagnostic session
- Check `confidence`: 1.0 means all mandatory modules responded; lower values mean some data is missing

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Overall status at a glance | `apoch_status` |
| Detailed problem list with severities | `apoch_health` |
| Event timeline | `apoch_history` |
| A prioritized next action | `apoch_recommend` |

---

### 2. apoch_health

**Purpose**: Get a detailed diagnosis of all active problems, their severity, and a per-problem suggested action.

**Human question answered**: *"What's broken and what should I do about it?"*

**What it does**:
- Queries Guardian (all diagnostics) — mandatory
- Queries Vision (module states) — optional enrichment

Guardian returns module-level diagnostics. Each diagnostic with `current_state == "FAILED"` becomes an ERROR-severity problem. Diagnostics with a non-null `last_error` but non-FAILED state become WARNING-severity problems.

Problems are sorted by severity (CRITICAL/ERROR first, then WARNING). The `suggested_action` is derived from the most severe problem.

**What it does NOT do**:
- Does NOT recommend global actions (use `apoch_recommend`)
- Does NOT show history (use `apoch_history`)
- Does NOT interpret productivity (use `apoch_progress` or `apoch_insights`)

**Parameters**: None.

**Examples**:

<details>
<summary>No problems — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "🟢 Sin problemas detectados",
  "healthy": true,
  "explanation": "No hay problemas registrados en el sistema",
  "evidence": [
    {"source": "Guardian", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"},
    {"source": "Vision", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": "Ninguna acción requerida",
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:05:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Problems detected — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "🔴 Se detectaron problemas críticos en el sistema",
  "healthy": false,
  "explanation": "[ERROR] chronicle: Connection refused to Chronicle store\n[WARNING] pulse: Data lag of 45 seconds detected",
  "evidence": [
    {"source": "Guardian", "confidence": 0.8, "collected_ago": 0, "based_on": "module response"}
  ],
  "suggested_action": "Revise el módulo chronicle. Puede intentar reiniciar el módulo o revisar su configuración.",
  "confidence": 0.5,
  "generated_at": "2026-07-17T12:05:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_DEPENDENCY_UNAVAILABLE` | Guardian (mandatory) did not respond. Vision-only data cannot produce a health diagnosis. |

**Confidence**:
- 1.0: Both Guardian and Vision responded
- 0.5: Only Guardian responded (Vision failed or is not loaded)

**Use cases**:
- Automated alerting — "check health, if ERROR then notify"
- Pre-deployment health gate
- Root cause investigation

**Best practices**:
- Check `summary` emoji first: 🟢 = healthy, 🟡 = warnings only, 🔴 = critical problems
- The `explanation` contains one line per problem formatted as `[SEVERITY] module: message`
- For warnings that may escalate: `suggested_action` will suggest proactive review

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Detailed problem list | `apoch_health` |
| Overall status (high level) | `apoch_status` |
| A prioritized recommendation | `apoch_recommend` |

---

### 3. apoch_history

**Purpose**: Get a chronological narrative of recent system activity — lifecycle events, tool invocations, and errors.

**Human question answered**: *"What has the system been doing?"*

**What it does**:
- Queries Chronicle only (single mandatory dependency)
- Returns a narrative of events (timestamped, grouped by type)
- Supports optional parameter filters

**What it does NOT do**:
- Does not consult Vision, Guardian, Pulse, Optimizer, or Oracle
- Does not show trends, metrics, or aggregations
- Does not interpret events or make recommendations
- Does not show raw log entries (use `apoch_logs`)
- `suggested_action` is always `None`

**Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `horas` | `int` | `24` | Number of past hours to query. Must be a positive integer. |
| `tipo` | `string` | `null` | Filter by event type. One of: `"lifecycle"`, `"tool"`, `"error"`. |

**Event type mapping**:

| `tipo` value | Internal Chronicle type |
|---|---|
| `"lifecycle"` | `"lifecycle"` (module start/stop/status changes) |
| `"tool"` | `"tool_invocation"` (tool call events) |
| `"error"` | `"error"` (errors and exceptions) |

**Examples**:

<details>
<summary>With events (default: last 24 hours) — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Se encontraron 5 eventos (lifecycle: 3, tool: 1, error: 1) en las últimas 24 horas",
  "explanation": "10:15 — Sistema de monitoreo operativo\n10:30 — Herramienta invocada: apoch_health\n11:00 — Sistema de diagnóstico operativo\n11:05 — Error: Timeout connecting to Chronicle store\n11:10 — Sistema de monitoreo operativo",
  "evidence": [
    {"source": "Chronicle", "confidence": 0.8, "collected_ago": 0, "based_on": "5 events"}
  ],
  "suggested_action": null,
  "confidence": 0.5,
  "generated_at": "2026-07-17T12:10:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>No events in the period — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "No hay actividad registrada en el período solicitado.",
  "explanation": "No hay actividad registrada en el período solicitado.",
  "evidence": [
    {"source": "Chronicle", "confidence": 0.8, "collected_ago": 0, "based_on": "0 events"}
  ],
  "suggested_action": null,
  "confidence": 0.3,
  "generated_at": "2026-07-17T12:10:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Filtered by errors — click to expand</summary>

Request: `{ "tipo": "error" }`

```json
{
  "api_version": "1.0",
  "summary": "Se encontraron 1 eventos (error: 1) en las últimas 24 horas",
  "explanation": "11:05 — Error: Timeout connecting to Chronicle store",
  "evidence": [
    {"source": "Chronicle", "confidence": 0.8, "collected_ago": 0, "based_on": "1 events"}
  ],
  "suggested_action": null,
  "confidence": 0.5,
  "generated_at": "2026-07-17T12:10:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_INVALID_ARGUMENT` | `horas` is not a positive integer, or `tipo` is not one of `"lifecycle"`, `"tool"`, `"error"`. |
| `ERR_DEPENDENCY_UNAVAILABLE` | Chronicle module is not loaded, failed, or timed out. |

**Confidence**:
- 0.50: Chronicle responded with at least one event
- 0.30: Chronicle responded but returned zero events

**Use cases**:
- "What happened while I was away?"
- Debugging a sequence of events leading to an error
- Audit trail

**Best practices**:
- Use `tipo` to narrow the scope — errors-only for incident investigation, lifecycle for startup issues
- The `explanation` field contains a line-by-line narrative with timestamps (HH:MM)
- Source names are user-facing aliases, not internal module names (e.g., `"Sistema de monitoreo"` instead of `"Vision"`)

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Event timeline | `apoch_history` |
| Raw debug log entries | `apoch_logs` |
| System status at a point in time | `apoch_status` |

---

### 4. apoch_recommend

**Purpose**: Get the single highest-impact action to take right now on the Apoch-AI platform.

**Human question answered**: *"What should I do next?"*

**What it does**:
The tool follows a deterministic fallback chain:

1. **Oracle available + has recommendations** → returns the top recommendation (highest priority, mapped to HIGH/MEDIUM/LOW)
2. **Oracle available but empty** → falls back to Guardian + Vision diagnostics
3. **Oracle unavailable** → falls back to Guardian + Vision diagnostics
4. **Guardian detects problems** → single recommendation from the worst problem (mapped: ERROR/CRITICAL → HIGH, WARNING → MEDIUM)
5. **Guardian + Vision healthy** → returns "No hay recomendaciones" with LOW priority
6. **All modules fail** → `ERR_TIMEOUT`

**What it does NOT do**:
- Does not return a list of recommendations — only the single best one
- Does not diagnose problems in detail (use `apoch_health`)
- Does not show system status (use `apoch_status`)

**Parameters**: None.

**Priority mapping**:

| Source | Input | Output priority |
|---|---|---|
| Oracle | `"critical"` or `"high"` | `HIGH` |
| Oracle | `"medium"` | `MEDIUM` |
| Oracle | `"low"` | `LOW` |
| Guardian (fallback) | `CRITICAL` or `ERROR` severity | `HIGH` |
| Guardian (fallback) | `WARNING` severity | `MEDIUM` |
| No issues | — | `LOW` |

**Examples**:

<details>
<summary>Oracle has a recommendation — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Optimizar configuración de Vision",
  "explanation": "El módulo Vision ha procesado un volumen creciente de solicitudes. Se recomienda ajustar el límite de concurrencia.",
  "evidence": [
    {"source": "Sistema de recomendaciones", "confidence": 0.8, "collected_ago": 0, "based_on": "recomendación priorizada"},
    {"source": "Diagnóstico del sistema", "confidence": 0.7, "collected_ago": 0, "based_on": "sin problemas detectados"}
  ],
  "suggested_action": null,
  "confidence": 0.85,
  "priority": "HIGH",
  "generated_at": "2026-07-17T12:15:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Fallback from Guardian problem — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Revisar módulo chronicle",
  "explanation": "[ERROR] chronicle: Connection refused to Chronicle store",
  "evidence": [
    {"source": "Diagnóstico del sistema", "confidence": 0.7, "collected_ago": 0, "based_on": "1 problema(s) activo(s)"}
  ],
  "suggested_action": null,
  "confidence": 0.5,
  "priority": "HIGH",
  "generated_at": "2026-07-17T12:15:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Everything healthy — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "No hay recomendaciones en este momento.",
  "explanation": "El sistema opera dentro de parámetros normales.",
  "evidence": [
    {"source": "Diagnóstico del sistema", "confidence": 0.7, "collected_ago": 0, "based_on": "sin problemas detectados"}
  ],
  "suggested_action": null,
  "confidence": 1.0,
  "priority": "LOW",
  "generated_at": "2026-07-17T12:15:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_TIMEOUT` | All queried modules (Oracle, Guardian, Vision) timed out or failed. |

**Use cases**:
- Agent deciding what to focus on next
- Proactive maintenance notifications
- CI/CD gating — "do not deploy if priority is HIGH"

**Best practices**:
- `priority` is the primary signal — HIGH means something needs attention
- `confidence` reflects the reliability of the source (Oracle rec confidence if available, 0.5 for fallback)
- When `priority` is LOW and the summary says "No hay recomendaciones", the system is healthy

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| A prioritized next action | `apoch_recommend` |
| All active problems with severities | `apoch_health` |
| System overview | `apoch_status` |

---

### 5. apoch_progress

**Purpose**: Understand how much work the system has done over a given period and whether productivity is trending up, down, or stable.

**Human question answered**: *"How productive has the system been lately?"*

**What it does**:
- Queries Pulse (mandatory dependency) for work unit data
- Queries Pulse trend data for comparison with a prior period
- Interprets the trend as one of: "creciente" (growing), "decreciente" (declining), "estable" (stable), or "baja" (low activity)
- Trend windows: `hoy` → compares with 1 prior day, `semana` → compares with 3 prior days, `mes` → compares with 15 prior days

**What it does NOT do**:
- Does not query system state, health, history, logs, or insights
- Does not expose raw Pulse data, WorkUnit IDs, model names, costs, or tokens
- Does not plan tasks or manage projects
- Does not recommend actions (`suggested_action` is always `None`)
- Does not interpret what the work units mean (use `apoch_insights`)

**Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `periodo` | `string` | `null` (last 24h) | One of: `"hoy"` (today), `"semana"` (last 7 days), `"mes"` (last 30 days). |

When `periodo` is `None`, the query covers the last 24 hours (rolling window, not calendar-day).

**Annual table: Period → data window and trend comparison window**:

| `periodo` | Data window | Trend comparison |
|---|---|---|
| `null` | Last 24 hours rolling | — |
| `"hoy"` | Calendar day (00:00 to now) | Compares with 1 prior day |
| `"semana"` | Last 7 days | Compares with 3 prior days |
| `"mes"` | Last 30 days | Compares with 15 prior days |

**Trend interpretation** (from `_interpret_progress_trend`):

| Condition | Trend label |
|---|---|
| Total count < 3 | `"baja"` — low activity |
| Recent > Previous in trend points | `"creciente"` — activity is increasing |
| Recent < Previous | `"decreciente"` — activity is decreasing |
| Recent == Previous | `"estable"` — stable |
| Only 1 trend point available | `"estable"` — no comparison possible |
| No data (empty list) | No trend — response says "No hay datos" |

**Examples**:

<details>
<summary>Productivity growing — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Productividad creciente",
  "explanation": "Se registraron 12 unidades de trabajo en el período solicitado. La actividad está aumentando en comparación con el período anterior.",
  "evidence": [
    {"source": "Sistema de rendimiento", "confidence": 0.8, "collected_ago": 0, "based_on": "12 unidades de trabajo"}
  ],
  "suggested_action": null,
  "confidence": 0.7,
  "generated_at": "2026-07-17T12:20:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Low activity — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Actividad baja",
  "explanation": "Se registraron 2 unidades de trabajo en el período solicitado. La actividad registrada es baja (2 unidades de trabajo en el período solicitado).",
  "evidence": [
    {"source": "Sistema de rendimiento", "confidence": 0.8, "collected_ago": 0, "based_on": "2 unidades de trabajo"}
  ],
  "suggested_action": null,
  "confidence": 0.5,
  "generated_at": "2026-07-17T12:20:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>No data — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "No hay datos de actividad para el período solicitado.",
  "explanation": "No hay datos de actividad en el período seleccionado.",
  "evidence": [
    {"source": "Sistema de rendimiento", "confidence": 0.3, "collected_ago": 0, "based_on": "0 unidades de trabajo"}
  ],
  "suggested_action": null,
  "confidence": 0.3,
  "generated_at": "2026-07-17T12:20:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_INVALID_ARGUMENT` | `periodo` is not `null`, `"hoy"`, `"semana"`, or `"mes"`. |
| `ERR_DEPENDENCY_UNAVAILABLE` | Pulse module is not loaded, failed, or timed out. |

**Confidence**:
- 0.7: Pulse list + trend data available (2+ trend points)
- 0.5: Data available but insufficient trend points
- 0.3: Pulse responded but had no data

**Use cases**:
- "Has activity dropped off?" — check for `baja` or `decreciente`
- Weekly productivity summary for a dashboard
- Detecting stagnation over time

**Best practices**:
- Start with no `periodo` for the last 24 hours, then expand to `"semana"` or `"mes"` for trend analysis
- Low confidence (0.3) with "No hay datos" likely means Pulse has no data for the selected period
- The trend label is in Spanish: `creciente`, `decreciente`, `estable`, `baja`

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Work unit count and trend | `apoch_progress` |
| Detected patterns and improvement areas | `apoch_insights` |
| Event timeline (what happened) | `apoch_history` |

---

### 6. apoch_insights

**Purpose**: Detect productivity patterns and improvement opportunities by analyzing Optimizer hypotheses enriched with Pulse activity data.

**Human question answered**: *"What patterns is the system showing that I should know about?"*

**What it does**:
- Queries Optimizer (mandatory) for hypotheses
- Filters to only `type == "pattern"` hypotheses (deterministic)
- Queries Pulse (optional) for activity context — enhances confidence when available
- Translates internal domains to user-facing concepts

**What it does NOT do**:
- Does not expose OptimizationHypothesis.evidence dict
- Does not expose module names, detector names, or internal stats
- Does not recommend actions (`suggested_action` is always `None`)
- Does not show work unit counts (use `apoch_progress`)
- Does not diagnose health problems (use `apoch_health`)

**Parameters**: None.

**Domain label mapping**:

| Internal domain | User-facing label |
|---|---|
| `"cost"` | `"costos"` |
| `"time"` | `"tiempo de trabajo"` |
| `"rework"` | `"reproceso"` |
| `"model_efficiency"` | `"eficiencia del modelo"` |
| `"session_behavior"` | `"comportamiento de sesión"` |

**Confidence formula**:

```
confidence = average(hypothesis.confidence) * pulse_factor
```

Where `pulse_factor` is:
- 1.0: Pulse data available and returned successfully
- 0.7: Pulse was queried but timed out or failed
- 0.5: Pulse module not available at all

**Examples**:

<details>
<summary>Patterns detected — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Se detectaron 2 patrones de productividad",
  "explanation": "Detecté un patrón en Vision que puede estar afectando tu tiempo de trabajo.\nDetecté un patrón en Pulse que puede estar afectando tu eficiencia del modelo.",
  "evidence": [
    {"source": "Sistema de optimización", "confidence": 0.8, "collected_ago": 0, "based_on": "2 patrón(es) detectado(s)"},
    {"source": "Sistema de rendimiento", "confidence": 0.7, "collected_ago": 0, "based_on": "38 unidades de trabajo"}
  ],
  "suggested_action": null,
  "confidence": 0.62,
  "generated_at": "2026-07-17T12:25:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>No patterns — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "No se detectaron patrones ni oportunidades de mejora.",
  "explanation": "No se detectaron patrones ni oportunidades de mejora.",
  "evidence": [
    {"source": "Sistema de optimización", "confidence": 0.8, "collected_ago": 0, "based_on": "sin patrones detectados"}
  ],
  "suggested_action": null,
  "confidence": 0.0,
  "generated_at": "2026-07-17T12:25:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_DEPENDENCY_UNAVAILABLE` | Optimizer module is not loaded, has no `optimizer.hypotheses` service, or timed out. |

**Use cases**:
- Proactive improvement — "the system found patterns, what should I investigate?"
- Long-term trend analysis of system behavior
- Identifying recurring inefficiencies

**Best practices**:
- Call `apoch_insights` periodically (e.g., once per session) to catch new patterns
- Combine with `apoch_progress` to understand if patterns correlate with productivity changes
- `confidence` of 0.0 means no patterns were found — that is not an error, just no data
- The `explanation` uses natural, agent-friendly language (e.g., "Detecté un patrón en...")

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Patterns and improvement opportunities | `apoch_insights` |
| Work unit count and productivity trend | `apoch_progress` |
| A prioritized next action | `apoch_recommend` |

---

### 7. apoch_logs

**Purpose**: Get raw debug log entries for system debugging — the closest thing to tailing a log file through MCP.

**Human question answered**: *"Show me the raw logs."*

**What it does**:
- Queries Vision (mandatory dependency) for recent log entries
- Applies module filter in memory (Vision.recent() does not support server-side module filtering)
- Returns formatted log lines with timestamp, level, module, and message

**What it does NOT do**:
- Does not show context, PIDs, or LogRecord objects (P6 compliance)
- Does not provide historical narrative (use `apoch_history`)
- Does not recommend actions (`suggested_action` is always `None`)

**Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `nivel` | `string` | `null` (all levels) | Filter by severity level. One of: `"INFO"`, `"WARN"`, `"ERROR"`, `"FATAL"`. |
| `limite` | `int` | `50` | Maximum number of entries to return. Must be a positive integer. When used with `modulo`, the limit applies AFTER the module filter. |
| `modulo` | `string` | `null` | Filter by module name. Applied in memory after Vision returns results. |

**Examples**:

<details>
<summary>All logs, default limit — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "Se encontraron 50 entradas de log",
  "explanation": "[2026-07-17T11:55:00] INFO [vision] — Module started\n[2026-07-17T11:55:01] INFO [guardian] — Diagnostics initialized\n[2026-07-17T11:55:02] INFO [chronicle] — Connected to store\n[2026-07-17T11:55:03] WARN [pulse] — Data lag detected\n[2026-07-17T11:55:04] INFO [optimizer] — Hypothesis engine ready\n...",
  "evidence": [
    {"source": "Sistema de monitoreo", "confidence": 0.8, "collected_ago": 0, "based_on": "50 entradas"}
  ],
  "suggested_action": null,
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:30:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>Filtered by ERROR level and a specific module — click to expand</summary>

Request: `{ "nivel": "ERROR", "modulo": "chronicle", "limite": 10 }`

```json
{
  "api_version": "1.0",
  "summary": "Se encontraron 2 entradas de log",
  "explanation": "[2026-07-17T11:05:00] ERROR [chronicle] — Connection refused to Chronicle store\n[2026-07-17T11:10:00] ERROR [chronicle] — Retry attempt 3/5 failed",
  "evidence": [
    {"source": "Sistema de monitoreo", "confidence": 0.8, "collected_ago": 0, "based_on": "2 entradas"}
  ],
  "suggested_action": null,
  "confidence": 1.0,
  "generated_at": "2026-07-17T12:30:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

<details>
<summary>No matching entries — click to expand</summary>

```json
{
  "api_version": "1.0",
  "summary": "No hay entradas de log que coincidan con los filtros especificados.",
  "explanation": "No hay entradas de log que coincidan con los filtros especificados.",
  "evidence": [
    {"source": "Sistema de monitoreo", "confidence": 0.8, "collected_ago": 0, "based_on": "0 entradas"}
  ],
  "suggested_action": null,
  "confidence": 0.3,
  "generated_at": "2026-07-17T12:30:00+00:00",
  "data_freshness": 0,
  "metadata": {}
}
```
</details>

**Possible errors**:

| Error | When |
|---|---|
| `ERR_INVALID_ARGUMENT` | `limite` is not a positive integer, or `nivel` is not one of `"INFO"`, `"WARN"`, `"ERROR"`, `"FATAL"`. |
| `ERR_DEPENDENCY_UNAVAILABLE` | Vision module is not loaded, has no `recent()` method, or timed out. |

**Confidence**:
- 1.0: At least one log entry matched the filters
- 0.3: Zero entries matched

**Use cases**:
- "The system had an error — show me the logs around that time"
- Deep debugging when `apoch_health` shows a problem but you need details
- Verifying that a module started or stopped

**Best practices**:
- Always filter by `nivel` when investigating problems — `ERROR` and `FATAL` first, then `WARN`
- Use `modulo` to narrow to the failing component (found via `apoch_health`)
- The `modulo` filter is applied in memory after Vision returns. If you need more results, increase `limite` to ensure enough entries are fetched before the memory filter
- Each log entry is formatted as `[timestamp] LEVEL [module] — message`. The format is stable across calls

**Comparison with similar tools**:

| If you need... | Use... |
|---|---|
| Raw log entries for debugging | `apoch_logs` |
| Event timeline (narrative) | `apoch_history` |
| System status overview | `apoch_status` |

---

## Legacy Aliases

### What they are

Legacy aliases are deprecated MCP tool names from earlier versions of Apoch-AI (< 1.0). They are **still registered and functional** for backward compatibility, but each call injects deprecation metadata into the response and will be removed in a future MAJOR version.

### Why they exist

Before PR8/PR9, the MCP tools were named after their internal modules (e.g., `vision_state`, `guardian_diagnostics`, `chronicle_query`). The PR9 release unified the API under the `apoch_*` naming convention to:

- Abstract away internal module names (P6 — no exposed implementation)
- Provide consistent naming (`apoch_*` prefix)
- Stabilize the tool surface for forward compatibility

### Registration order

Legacy aliases are registered **after** coordinator tools and **before** module-specific tools (sorted alphabetically), per `src/apoch/adapters/manager.py`.

### Complete alias table

| Legacy name | Maps to | Handler | Deprecated since |
|---|---|---|---|
| `vision_state(module?)` | `apoch_status` | `legacy_vision_state` | 1.0 |
| `chronicle_query(source, event_type, since, until, limit)` | `apoch_history` | `legacy_chronicle_query` | 1.0 |
| `guardian_diagnostics(module_name)` | `apoch_health` | `legacy_guardian_diagnostics` | 1.0 |
| `guardian_all_diagnostics()` | `apoch_health` | `legacy_guardian_all_diagnostics` | 1.0 |
| `vision_logs(limit=50, level)` | `apoch_logs` | `legacy_vision_logs` | 1.0 |

### Parameter mapping details

#### chronicle_query → apoch_history

| Legacy param | Mapping | Notes |
|---|---|---|
| `event_type` | `tipo` | `"tool_call"` → `"tool"`, `"error"` → `"error"`, `"lifecycle"` → `"lifecycle"`, `"state_change"` → `"lifecycle"` |
| `since` (ISO 8601) | `horas` | Computed as `max(1, delta_hours)` between `since` and now. Invalid dates produce `null` (uses default 24h). |
| `source` | — | **Ignored.** |
| `until` | — | **Ignored.** |
| `limit` | — | **Ignored.** Always returns up to 50 events. |

#### vision_logs → apoch_logs

| Legacy param | Maps to | Notes |
|---|---|---|
| `limit` (default 50) | `limite` | Direct pass-through. |
| `level` | `nivel` | Direct pass-through. |

### Deprecation metadata

Every response through a legacy alias includes:

```json
"metadata": {
  "legacy_tool": "vision_state",
  "replaced_by": "apoch_status",
  "deprecated_since": "1.0"
}
```

### Migration path

Replace legacy tool names with their modern equivalents in your agent configuration:

| If you call... | Replace with... |
|---|---|
| `vision_state` | `apoch_status` |
| `chronicle_query` | `apoch_history` |
| `guardian_diagnostics("module")` | `apoch_health` |
| `guardian_all_diagnostics` | `apoch_health` |
| `vision_logs` | `apoch_logs` |

---

## Migration Guide

### Step 1: Identify legacy usage

Search your agent configuration or client code for `vision_state`, `chronicle_query`, `guardian_diagnostics`, `guardian_all_diagnostics`, or `vision_logs`.

### Step 2: Replace tool names

**Before (legacy):**

```python
# Old way — module-specific names
result = await client.call_tool("vision_state", {})
result = await client.call_tool("chronicle_query", {"event_type": "error", "since": "2026-07-16T00:00:00Z"})
result = await client.call_tool("guardian_diagnostics", {"module_name": "chronicle"})
result = await client.call_tool("guardian_all_diagnostics", {})
result = await client.call_tool("vision_logs", {"level": "ERROR", "limit": 20})
```

**After (modern):**

```python
# New way — unified apoch_* naming
result = await client.call_tool("apoch_status", {})
result = await client.call_tool("apoch_history", {"tipo": "error", "horas": 24})
result = await client.call_tool("apoch_health", {})
result = await client.call_tool("apoch_health", {})

# No need for guardian_all_diagnostics — apoch_health always returns all diagnostics
result = await client.call_tool("apoch_logs", {"nivel": "ERROR", "limite": 20})
```

### Step 3: Update parameter names

| Legacy parameter | Modern parameter | Notes |
|---|---|---|
| `event_type` | `tipo` | Enum values changed: `"tool_call"` → `"tool"`, `"state_change"` → `"lifecycle"` |
| `since` | `horas` | Compute hours yourself for more control, or let the legacy alias do it |
| `level` | `nivel` | Same values: `"INFO"`, `"WARN"`, `"ERROR"`, `"FATAL"` |
| `limit` | `limite` | Same behavior, same default (50) |
| `module_name` | N/A | `apoch_health` always returns diagnostics for all modules |
| `module` (vision_state) | N/A | `apoch_status` always returns all module states |
| `source` (chronicle_query) | N/A | No longer exposed |
| `until` (chronicle_query) | N/A | Use `horas` to define the window |

### Step 4: Update response handling

Legacy tools return the same `ToolResponse` format as modern tools, so response parsing does not need to change. The only difference is the `metadata` field: legacy responses include `legacy_tool`, `replaced_by`, and `deprecated_since` keys. Modern tools return `metadata: {}`.

### Step 5: Test and verify

1. Run your existing agent workflow with legacy aliases — they still work.
2. Switch to modern names in a test environment.
3. Compare responses for equivalent calls (same data should produce the same results).
4. Deploy the updated configuration.

### Key differences to watch for

| Aspect | Legacy | Modern |
|---|---|---|
| Tool naming | Module-specific (`vision_state`, `guardian_diagnostics`) | Unified (`apoch_status`, `apoch_health`) |
| Multiple-health tools | Two separate tools (`guardian_diagnostics`, `guardian_all_diagnostics`) | Single tool (`apoch_health`) |
| History params | Five parameters (`source`, `event_type`, `since`, `until`, `limit`) | Two parameters (`horas`, `tipo`) |
| Response metadata | Includes `legacy_tool`, `replaced_by`, `deprecated_since` | `metadata: {}` |

---

## Error Catalog

All 9 error codes are defined in `src/apoch/public_api/errors.py`.

| Code | Meaning | Typical causes | Recommended action |
|---|---|---|---|
| `ERR_TIMEOUT` | One or more modules did not respond within the configured timeout. | Network issue, module stuck, module not started. | Check module health with `apoch_health`. Increase timeouts if modules are slow. |
| `ERR_NO_DATA` | No data available to answer the query. | Chronicle or Pulse have no data for the requested period. | Broaden the query window. Verify the module has been running long enough. |
| `ERR_NOT_INITIALIZED` | The system has not been started yet. | `AgentAdapterManager.start()` was not called. | Start the system before calling tools. |
| `ERR_DEPENDENCY_UNAVAILABLE` | A required internal module is not loaded or has failed. | Module not configured, startup failed, module crashed. | Check the module's configuration. Restart the system. Check `apoch_health`. |
| `ERR_PERMISSION_DENIED` | The caller does not have permission for this operation. | MCP client not authorized. Reserved for future auth integration. | Verify MCP client credentials. |
| `ERR_INVALID_ARGUMENT` | One or more arguments are invalid or out of range. | Wrong tipo, periodo, nivel, horas, or limite values. | Check parameter constraints in this document. |
| `ERR_INTERNAL` | Unexpected internal error that could not be categorized. | Bug, unhandled exception, data corruption. | Check logs. Report the issue if it persists. |
| `ERR_UNKNOWN` | Unclassified error — last resort. Always investigate. | Truly unexpected path reached. | Check logs and report the bug. |
| `ERR_NOT_IMPLEMENTED` | The requested tool functionality has not been implemented. | Referenced a tool that is defined in spec but not yet coded. | Do not use this tool in production. Check the changelog for availability. |

### Error response structure

Every error returns:

```json
{
  "ok": false,
  "error": {
    "code": "ERR_DEPENDENCY_UNAVAILABLE",
    "message": "No se pudo consultar el historial de actividad"
  }
}
```

Error messages are in Spanish (the system's locale). This is the complete MCP response — no additional envelope wrapping.

---

## API Reference

### Tool overview

| Tool | Parameters | Dependencies (required → optional) | Returns |
|---|---|---|---|
| `apoch_status` | None | Vision, Guardian, Chronicle → Oracle | `ToolResponse` |
| `apoch_health` | None | Guardian → Vision | `ToolResponse` |
| `apoch_history` | `horas: int?`, `tipo: string?` | Chronicle | `ToolResponse` |
| `apoch_recommend` | None | Oracle (preferred), Guardian, Vision | `RecommendResponse` |
| `apoch_progress` | `periodo: string?` | Pulse | `ToolResponse` |
| `apoch_insights` | None | Optimizer → Pulse | `ToolResponse` |
| `apoch_logs` | `nivel: string?`, `limite: int?`, `modulo: string?` | Vision | `ToolResponse` |

### Parameter details

| Parameter | Applies to | Type | Valid values | Default |
|---|---|---|---|---|
| `horas` | `apoch_history` | `int` | Positive integers | `24` |
| `tipo` | `apoch_history` | `string` | `"lifecycle"`, `"tool"`, `"error"` | `null` (all types) |
| `periodo` | `apoch_progress` | `string` | `"hoy"`, `"semana"`, `"mes"` | `null` (last 24h) |
| `nivel` | `apoch_logs` | `string` | `"INFO"`, `"WARN"`, `"ERROR"`, `"FATAL"` | `null` (all levels) |
| `limite` | `apoch_logs` | `int` | Positive integers | `50` |
| `modulo` | `apoch_logs` | `string` | Any module name | `null` (all modules) |

### Response fields

| Field | Type | Appears in | Description |
|---|---|---|---|
| `api_version` | `string` | All tools | The API contract version (`"1.0"`) |
| `summary` | `string` | All tools | One-line human-readable answer |
| `explanation` | `string` | All tools | Contextual detail (may span multiple lines) |
| `evidence` | `list` | All tools | Array of `EvidenceSource` dicts |
| `suggested_action` | `string` or `null` | All tools | Recommended next step, or `null` |
| `confidence` | `float` | All tools | 0.00–1.00 |
| `generated_at` | `string` (ISO 8601) | All tools | UTC timestamp |
| `data_freshness` | `int` | All tools | Age in seconds (always `0` in v1.0) |
| `metadata` | `dict` | All tools | Extensibility (legacy metadata when called through an alias) |
| `priority` | `string` | `apoch_recommend` | `"HIGH"`, `"MEDIUM"`, or `"LOW"` |
| `expected_benefit` | `string` or `null` | `apoch_recommend` | Projected impact (always `null` in v1.0) |

### EvidenceSource fields

| Field | Type | Description |
|---|---|---|
| `source` | `string` | Module name or functional label (varies by tool — see evidence section) |
| `confidence` | `float` | Source reliability (currently fixed at `0.8` for responding modules) |
| `collected_ago` | `int` | Seconds since collection (currently always `0`) |
| `based_on` | `string` | What data was used (e.g., `"5 events"`, `"38 unidades de trabajo"`) |

### Timeouts

| Module | Default timeout | Tools that query it |
|---|---|---|
| Vision | 1.0s | `status`, `health`, `recommend`, `logs` |
| Guardian | 0.5s | `status`, `health`, `recommend` |
| Chronicle | 0.5s | `status`, `history` |
| Oracle | 2.0s | `status`, `recommend` |
| Pulse | 0.5s | `progress`, `insights` |
| Optimizer | 1.0s | `insights` |

---

## FAQ

**Q: Why do some tools have confidence lower than 1.0?**

Confidence reflects how many of the queried modules responded successfully. When optional modules time out or are not loaded, confidence decreases proportionally. See each tool's section for the exact formula.

**Q: What does `suggested_action: null` mean?**

It means the tool is a "pure query" — it only returns information and does not recommend an action. This applies to `apoch_history`, `apoch_progress`, `apoch_insights`, and `apoch_logs`. `apoch_status` and `apoch_health` always provide a suggested action (even if it's "no action needed").

**Q: Why are error messages in Spanish?**

Apoch-AI's default locale is Spanish. Error messages follow the same locale. The error `code` is language-independent and should be used for programmatic handling.

**Q: How do I distinguish between "no data" and "error"?**

- "No data" is a **successful** response with no results — `confidence` is low (0.3) and `summary` explicitly says "No hay...". For example, `apoch_history` returns `"No hay actividad registrada..."` — this is not an error.
- An **error** response has `ok: false` with an error code. For example, `ERR_DEPENDENCY_UNAVAILABLE` means a required module could not be queried.

**Q: Can I pass `horas=0` to `apoch_history`?**

No. `horas` must be a positive integer. Passing `0` or a negative number returns `ERR_INVALID_ARGUMENT`.

**Q: Can I pass `limite=0` to `apoch_logs`?**

No. `limite` must be a positive integer. Passing `0` or a negative number returns `ERR_INVALID_ARGUMENT`.

**Q: What is the difference between `apoch_history` and `apoch_logs`?**

`apoch_history` returns a curated narrative of events (lifecycle changes, tool invocations, errors) with natural-language descriptions. It summarizes and groups events. `apoch_logs` returns raw debug log entries with timestamps, levels, and module names. Use `history` for "what happened" and `logs` for "show me the raw data."

**Q: What happens if I call a legacy alias?**

It works exactly the same as the modern equivalent, but the response `metadata` will contain `legacy_tool`, `replaced_by`, and `deprecated_since` fields. The tool description in the MCP registry also starts with `[DEPRECATED]`.

**Q: Will legacy aliases be removed?**

Yes, in a future MAJOR version (2.0+). The deprecation notice has been in place since version 1.0.

**Q: Are there rate limits on the MCP API?**

No. The MCP API is local (stdio transport). Rate limits may be added in future versions if the API is exposed over a network transport.

**Q: Can I use `modulo` with `nivel` in `apoch_logs` at the same time?**

Yes. When both are specified, Vision first filters by `nivel`, then the in-memory filter narrows by `modulo`, and finally the `limite` is applied. For example, with `nivel: "ERROR", modulo: "chronicle", limite: 10`, you get up to 10 ERROR-level entries from the `chronicle` module.

---

## Best Practices

### Diagnostic workflow

Use tools in this order when investigating an issue:

1. **`apoch_status`** — quick check: is the system running? Are there problems?
2. **`apoch_health`** — if there are problems, get the detailed list with severities
3. **`apoch_logs`** — for ERROR-level diagnostics, pull the raw logs with `nivel: "ERROR"` and optionally `modulo` set to the failing module
4. **`apoch_history`** — understand the sequence of events leading to the failure

### Confidence as a signal

- `confidence == 1.0`: All expected modules responded. Trust the answer.
- `confidence < 1.0 && > 0.0`: Partial data. Some modules failed or timed out. The answer is based on what was available.
- `confidence == 0.0`: No data found (not an error). For `apoch_insights`, this means no patterns were detected.
- Error response: Something went wrong. Handle by code, not by message text.

### Error handling

Always check for `ok: false` before processing ToolResponse fields. Handle errors by `code`, not by `message` text:

```python
result = await client.call_tool("apoch_health", {})
if not result.get("ok", True):
    code = result["error"]["code"]
    if code == "ERR_DEPENDENCY_UNAVAILABLE":
        # Handle gracefully — report that health data is unavailable
    elif code == "ERR_TIMEOUT":
        # Retry after a delay
```

### Parameter hygiene

- Always provide `limite` explicitly in `apoch_logs` to avoid surprises from the default (50)
- Use `tipo` in `apoch_history` to keep responses focused — errors-only for debugging
- Use `periodo` in `apoch_progress` to get meaningful trend comparisons

### Performance

- Module-level **timeouts** are generous for safety: Oracle gets 2s, others 0.5–1s
- Tools that query multiple modules in parallel (`status`, `health`, `recommend`) complete in approximately the slowest module's timeout
- Single-module tools (`history`, `progress`, `insights`, `logs`) complete in their module's timeout (0.5–1s)

### Agent usage

When building an AI agent that uses these tools:

1. **Start with `apoch_status`** at the beginning of every interaction to ground the agent in the current state
2. **Use `apoch_recommend`** for action planning — the agent can follow the recommended action or provide reasoning for a different choice
3. **Use `apoch_progress` + `apoch_insights`** together for session-level awareness — what was done and what patterns were detected
4. **Do NOT call `apoch_logs`** unless the agent is actively debugging — it returns verbose raw data
5. **Handle `ERR_TIMEOUT`** by retrying once after a short delay; if it persists, alert the user

---

## Changelog

### PR10 — MCP Public API documentation (current)

- Complete documentation for all 7 public MCP tools
- ToolResponse, ErrorResponse, EvidenceSource, and RecommendResponse contracts documented
- Error catalog with all 9 error codes
- Legacy alias documentation and migration guide
- FAQ and best-practices sections

### PR9 — Legacy aliases and deprecation

- Added 5 legacy aliases: `vision_state`, `chronicle_query`, `guardian_diagnostics`, `guardian_all_diagnostics`, `vision_logs`
- All legacy tools inject `metadata.legacy_tool`, `metadata.replaced_by`, `metadata.deprecated_since`
- Legacy tool descriptions prefixed with `[DEPRECATED]`
- Registration order: coordinator tools → legacy aliases → module tools (sorted)

### PR8 — Core public tools

- Implemented `apoch_logs` tool with `nivel`, `limite`, `modulo` parameters
- Implemented `apoch_insights` tool with Optimizer + Pulse orchestration
- Consolidated coordinator to exactly 7 public tools
- All tools return `ToolResponse` dict (or `RecommendResponse` for `apoch_recommend`)
- All errors use the centralized error catalog

---

*Documentation generated from the Apoch-AI codebase at `src/apoch/public_api/`. For implementation details, see `coordinator.py`, `models.py`, `errors.py`, `version.py`, and `registry.py`.*
