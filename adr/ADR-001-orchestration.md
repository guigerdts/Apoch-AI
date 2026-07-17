# ADR-001 — Orchestration & Service Registry

**Date:** 2026-07-14
**Status:** Approved
**Context:** The MCP Public API requires a coordinator that queries multiple internal modules (Vision, Guardian, Chronicle, Oracle) in parallel, aggregates their responses, and builds a unified ToolResponse. The coordinator must know which modules are available at runtime without hardcoding module names.

---

## 1. Objective

### 1.1 What this ADR guarantees

- The `ApochCoordinator` is the **single entry point** for all public MCP tools.
- Module dependencies are injected via `ServiceRegistry` — the coordinator never imports modules directly.
- Tools are registered via `ToolDef` lists, not hardcoded in the coordinator.
- The coordinator remains module-agnostic (zero imports from `apoch.modules.*`).

### 1.2 What is out of scope

- Module lifecycle management (covered by `Engine` and `ModuleRegistry` in `apoch.core`).
- Adapter registration for non-MCP tooling.

---

## 2. ServiceRegistry

The `ServiceRegistry` is a plain dataclass that holds optional references to each module's public API:

```python
@dataclass
class ServiceRegistry:
    vision: VisionModule | None = None
    guardian: GuardianModule | None = None
    chronicle: ChronicleModule | None = None
    oracle: OracleModule | None = None
```

The `Engine` populates this registry at startup by gathering `services` from each loaded module. The coordinator receives it via constructor injection.

---

## 3. ApochCoordinator

Every public tool method follows the same orchestration pattern:

1. Build a list of `(module_key, coroutine, timeout)` tuples.
2. Run all queries in parallel via `asyncio.gather()` with individual timeouts.
3. Aggregate results into a `ToolResponse` with `EvidenceSource` entries for modules that responded.
4. Handle timeouts gracefully — failed modules return `None` and are omitted from evidence.

### Tool registration

Tools register via `ToolDef` lists (see `get_tool_defs()` and `get_legacy_aliases()` on `ApochCoordinator`). The `AgentAdapterManager` calls these methods at startup and registers each tool with the MCP gateway.

---

## 4. Consequences

- Adding a new module requires: (a) adding it to `ServiceRegistry`, (b) wiring it in the Engine, (c) adding query logic in the coordinator. No other changes needed.
- Removing a module: the coordinator degrades gracefully — the module key returns `None` for all queries.
