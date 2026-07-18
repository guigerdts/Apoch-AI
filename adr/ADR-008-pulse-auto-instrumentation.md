# ADR-008 — Pulse Auto-Instrumentation

**Date:** 2026-07-18
**Status:** Approved
**Context:** Pulse measures engineering productivity but requires explicit `record()` calls. Without auto-instrumentation, Pulse starts empty and provides no value until modules are modified to emit measurements. We need transparent instrumentation that captures system events as Pulse measurements without modifying any existing module.

---

## 1. Objective

### 1.1 What this ADR guarantees

- System events (tool calls, engine lifecycle) are transparently captured as Pulse measurements.
- No existing module is modified to emit events — 100% backward compatible.
- EventBus is the sole communication channel: EventTopics constants, SystemEvent frozen model.
- Infinite feedback loops are prevented via auto-exclusion (source="pulse" is skipped).
- Core (`apoch/core/`) remains import-free of `modules/` and `public_api/`.

### 1.2 What is out of scope

- Module-to-module events (future concern).
- Event filtering, routing, or transformation beyond pulse recording.
- Aggregation, analysis, or recommendation based on captured data.

---

## 2. Architecture Decisions

### 2.1 EventTopics as Class Constants

**Decision:** All event topic strings are defined as class constants on `EventTopics` in `apoch/core/events.py`.

**Rationale:** Eliminates free-string typos, enables IDE autocompletion, provides a single source of truth for all event topics. Each constant maps to a dotted-string value (e.g. `tool.completed`).

### 2.2 SystemEvent as Frozen Dataclass

**Decision:** `SystemEvent` is a frozen (`@dataclass(frozen=True)`) data class with fields: `event_id` (uuid4.hex), `topic` (str), `source` (str), `timestamp` (ISO 8601 UTC), `payload` (dict).

**Rationale:** Immutability guarantees that once an event is emitted, its content cannot be mutated by downstream handlers. UUID-based `event_id` enables deduplication. The `payload` dict is open-ended — handlers receive the event object plus unpacked payload kwargs.

### 2.3 EventBus in Context, NOT ServiceRegistry

**Decision:** The `event_bus` reference is added as a field on the `Context` dataclass, not on `ServiceRegistry`.

**Rationale:** `Context` is the natural carrier for runtime infrastructure that modules receive during `start()`. Adding it to `ServiceRegistry` would couple the public API layer to the event system, which violates layering. Modules access the bus via `context.event_bus` during startup if they need to subscribe.

### 2.4 PulseEventSubscriber as Standalone Class

**Decision:** `PulseEventSubscriber` is a standalone class in `apoch/modules/pulse/events.py`, NOT a method or subclass inside `PulseModule`.

**Rationale:** SRP — PulseModule handles measurement orchestration (record, query, analysis). PulseEventSubscriber handles event subscription. They communicate via `record_fn` (dependency injection), not inheritance. This keeps both classes testable in isolation.

### 2.5 Handler Registry Dict (No if/elif Chains)

**Decision:** Event dispatch inside `PulseEventSubscriber` uses a `dict[str, Callable]` keyed by `EventTopics` constant.

**Rationale:** O(1) dispatch, no branching logic, easy to extend. Adding a new event type requires adding an entry to the dict and implementing a handler method — no chain modification.

### 2.6 Auto-Exclusion (Feedback Loop Prevention)

**Decision:** Events with `source == "pulse"` are skipped by every handler in `PulseEventSubscriber`.

**Rationale:** Without this guard, any measurement recorded by Pulse (which also emits events) would be re-captured, creating an infinite feedback loop. The source check is a single `if` at the top of each handler.

### 2.7 Coordinator Tool Events via EventBus

**Decision:** `ApochCoordinator` accepts an optional `event_bus` parameter. When set, all 7 public tool methods emit `TOOL_INVOCATION` before processing and `TOOL_COMPLETED`/`TOOL_ERROR` on result.

**Rationale:** Transparent instrumentation of all tool calls without modifying the method body's business logic. Event emission is a cross-cutting concern handled by wrapper methods at the start and return points of each tool method.

---

## 3. Event Flow

```
Engine.start()
  ├─ emit ENGINE_STARTED (plain string, backward compat)
  ├─ emit MODULE_STARTED (SystemEvent) per RUNNING module
  └─ emit MODULE_FAILED (SystemEvent) per FAILED module

Engine.stop()
  ├─ emit ENGINE_STOPPING (plain string)
  └─ emit MODULE_STOPPED (SystemEvent) per RUNNING module

ApochCoordinator.status()
  ├─ emit TOOL_INVOCATION (SystemEvent)
  ├─ ... process ...
  └─ emit TOOL_COMPLETED | TOOL_ERROR (SystemEvent)

PulseEventSubscriber
  ├─ subscribes to: TOOL_COMPLETED, ENGINE_STARTED, ENGINE_STOPPING
  ├─ each handler: skip if source == "pulse"
  ├─ transforms to MeasurementInput
  └─ calls record_fn()
       └─ PulseStore.save() — catches StorageError (dedup)
```

---

## 4. Chain Strategy

This ADR is implemented as PR-1 of a 4-PR plan:

| PR | Focus | Lines |
|----|-------|-------|
| PR-1 (this) | Auto-instrumentation infrastructure | ~500 |
| PR-2 | Pulse progress/insights integration | ~300 |
| PR-3 | Optimizer/Oracle pulse data consumption | ~400 |
| PR-4 | CLI and dashboard pulse data exposure | ~350 |

PR-1 is granted a **size exception** because it's already sliced as part of a larger plan.

---

## 5. Key Design Constraints

- EventBus in Context, NOT ServiceRegistry
- EventTopics as class constants, NOT free strings
- PulseEventSubscriber as standalone class, NOT inside PulseModule
- SystemEvent is frozen dataclass
- Handler registry dict, NOT if/elif chains
- No existing module modified to emit events
- Auto-exclusion: `source="pulse"` skipped
- Dedup via existing PulseStore ID uniqueness
- All existing tests must pass without changes
- Core (`apoch/core/`) must NOT import from `modules/` or `public_api/`
- No ServiceRegistry changes
