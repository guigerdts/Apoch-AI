# ADR-003 — EvidenceSource Contract

**Date:** 2026-07-14
**Status:** Approved
**Context:** Every MCP Public API tool must attribute its answer to specific data sources. Users need to know which modules contributed, how reliable each source is, and how fresh the data is — without exposing internal module names or implementation details.

---

## 1. Objective

### 1.1 What this ADR guarantees

- Every `ToolResponse` includes an `evidence` array of `EvidenceSource` entries.
- Each entry records: source label, confidence, age, and basis description.
- The coordinator decides which naming convention to use per tool (module name or functional label).

### 1.2 What is out of scope

- Confidence scoring formulas (per-tool, defined in each tool's implementation).
- Data freshness tracking (currently always 0 — live queries).

---

## 2. EvidenceSource

```python
@dataclass
class EvidenceSource:
    source: str         # "Vision", "Guardian", "Chronicle", "Oracle" or functional label
    confidence: float   # 0.00–1.00 (currently fixed at 0.8 per module)
    collected_ago: int  # Seconds since collection (currently always 0)
    based_on: str       # Description of the data used
```

---

## 3. Naming Conventions

| Convention | Tools | Examples |
|---|---|---|
| **Module names** | `status`, `health`, `history`, `progress`, `insights`, `logs` | `"Vision"`, `"Guardian"`, `"Chronicle"`, `"Oracle"` |
| **Functional labels** | `recommend` | `"Sistema de recomendaciones"`, `"Diagnóstico del sistema"` |

Module names are the default — `_build_evidence()` uses `key.capitalize()` on the module key. `recommend` uses `_build_recommend_evidence()` with functional labels (per architecture constraint P6 — no exposed implementation).

---

## 4. Consequences

- Adding a new tool needs an evidence builder — either reuse `_build_evidence` or write a custom one.
- Module names are visible in some tool responses (P6 exemption for status/health/history).
