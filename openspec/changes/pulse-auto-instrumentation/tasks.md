# Tasks: Pulse Auto-Instrumentation (PR-1)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~500–600 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (already PR-1 of 4-PR plan) |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

### Suggested Work Units

Not needed — this is already a sliced PR (PR-1 of a 4-PR plan). Delivery strategy `exception-ok` accepts the size.

## Phase 1: Event Infrastructure

- [x] 1.1 **EventTopics constants** — Add `EventTopics` class with 8 constants to `src/apoch/core/events.py`. Fields: `ENGINE_STARTED`, `ENGINE_STOPPING`, `MODULE_STARTED`, `MODULE_STOPPED`, `MODULE_FAILED`, `TOOL_INVOCATION`, `TOOL_COMPLETED`, `TOOL_ERROR`. No behavioral changes. Tests: verify constants match spec values.
- [x] 1.2 **SystemEvent immutable model** — Add frozen dataclass `SystemEvent` to `src/apoch/core/events.py` with fields: `event_id` (str, uuid4.hex), `topic` (str), `source` (str), `timestamp` (str, ISO 8601 UTC), `payload` (dict). Tests: verify frozen, constructor, topic matches EventTopics constant.
- [x] 1.3 **Context.event_bus field** — Add `event_bus: EventBus | None = None` to `Context` dataclass in `src/apoch/core/module.py`. No behavioral change. Tests: verify field exists, defaults to None.

## Phase 2: Engine + EventBus Wiring

- [x] 2.1 **EventBus SystemEvent support** — Overload `EventBus.emit()` in `src/apoch/core/events.py` to accept `str | SystemEvent`. When `str`: existing behavior unchanged (backward compat). When `SystemEvent`: dispatch by `event.topic`, pass all `event.payload` items as kwargs. Tests: verify both paths, existing tests pass unchanged.
- [x] 2.2 **Engine passes event_bus to Context** — In `src/apoch/core/engine.py`, set `context.event_bus = self._events` before calling `start_all()`. Tests: verify context.event_bus is set during module start.
- [x] 2.3 **Engine module lifecycle events** — After `start_all()` completes, emit `MODULE_STARTED` for each RUNNING module; after `stop_all()`, emit `MODULE_STOPPED` for each stopped module; emit `MODULE_FAILED` for any module in FAILED state. Use SystemEvent with source set to module name. Tests: verify events emitted with correct topic and source.

## Phase 3: PulseEventSubscriber

- [x] 3.1 **PulseEventSubscriber class** — New file `src/apoch/modules/pulse/events.py`. Standalone class (not inside PulseModule). Constructor accepts `event_bus: EventBus` and `record_fn: Callable`. `start()` subscribes to `TOOL_COMPLETED`, `ENGINE_STARTED`, `ENGINE_STOPPING`. Each handler constructs `MeasurementInput` with stable `work_unit_id` from `event.event_id` and calls `record_fn`. Tests: subscriber registers on start, handlers transform events correctly.
- [x] 3.2 **Handler registry dict** — Inside `PulseEventSubscriber`, dispatch via `dict[str, Callable]` keyed by `EventTopics` constant. No if/elif chains. Tests: unhandled topic silently ignored, unknown topic logs nothing at WARNING+.
- [x] 3.3 **Auto-exclusion + dedup** — Skip events with `source == "pulse"` in every handler. Catch `StorageError` from `record_fn`, log at DEBUG, do NOT propagate. Tests: pulse-sourced events skipped, duplicate event_id logged at DEBUG only.
- [x] 3.4 **Pulse __init__ update** — Add `PulseEventSubscriber` lazy import in `src/apoch/modules/pulse/__init__.py` following existing pattern. Add to `__all__`.

## Phase 4: Coordinator + Manager Wiring

- [x] 4.1 **Coordinator accepts event_bus** — Add optional `event_bus: EventBus | None = None` parameter to `ApochCoordinator.__init__` in `src/apoch/public_api/coordinator.py`. Store as `self._event_bus`. Tests: constructed without event_bus works (backward compat), constructed with event_bus stores it.
- [x] 4.2 **Coordinator tool events** — Wrap each public tool method (`status`, `health`, `history`, `recommend`, `progress`, `insights`, `logs`) with `TOOL_INVOCATION` emit before processing, `TOOL_COMPLETED` on success, `TOOL_ERROR` on error response. Emit only when `self._event_bus` is not None. Tests: all 3 events emitted, source="coordinator", payload includes tool name, backward compat without event_bus.
- [x] 4.3 **Manager wires subscriber + coordinator bus** — In `src/apoch/adapters/manager.py`, after Coordinator creation, instantiate `PulseEventSubscriber(event_bus, pulse_module.record)` and call `.start()`. Pass `engine.events` to `ApochCoordinator`. Pulse module reference obtained from `loaded["pulse"]`. Tests: subscriber started after coordinator, correct references passed.

## Phase 5: Integration Tests

- [x] 5.1 **Full integration test** — New test file `tests/test_pulse_auto_instrumentation.py`. Test end-to-end: create EventBus, PulseModule, PulseEventSubscriber, Coordinator. Verify subscriber → MeasurementInput → PulseStore. Verify auto-exclusion (source=pulse ignored). Verify dedup (same event_id logged at DEBUG, no crash). Verify all existing tests still pass.

## Phase 6: Documentation

- [x] 6.1 **ADR-008** — Create `adr/ADR-008-pulse-auto-instrumentation.md` documenting: EventBus SystemEvent support, EventTopics constants pattern, PulseEventSubscriber architecture, auto-exclusion design, chain strategy decisions.
- [x] 6.2 **Changelog** — Add `[0.9.2-alpha]` or appropriate next-version entry in `CHANGELOG.md` under a new `### Added` section describing the auto-instrumentation feature.

## Phase Organization Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1 | 1.1–1.3 | Event types + Context field |
| Phase 2 | 2.1–2.3 | Engine + EventBus wiring |
| Phase 3 | 3.1–3.4 | PulseEventSubscriber |
| Phase 4 | 4.1–4.3 | Coordinator + Manager wiring |
| Phase 5 | 5.1 | Integration tests |
| Phase 6 | 6.1–6.2 | Documentation |

### Dependency Graph

```
1.1 EventTopics ──→ 1.2 SystemEvent ──→ 2.1 EventBus emit overload
                                              │
                           1.3 Context.event_bus
                              │
                              2.2 Engine passes bus ──→ 2.3 Lifecycle events
                                                              │
                                         3.1 PulseEventSubscriber ←──┘
                                              │
                                    3.2 Handler dict ←── 3.3 Auto-exclusion + dedup
                                                              │
                                         4.1 Coordinator bus param
                                              │
                                    4.2 Tool events ────┐
                                                         │
                                         4.3 Manager wiring ──┘
                                                              │
                                                   5.1 Integration tests
                                                              │
                                                   6.1 ADR + 6.2 Changelog
```

### Key Design Constraints (Frozen — Do Not Reopen)

- EventBus in Context, NOT ServiceRegistry
- EventTopics as class constants, NOT free strings
- PulseEventSubscriber as standalone class, NOT inside PulseModule
- SystemEvent is frozen dataclass
- Handler registry dict, NOT if/elif chains
- No existing module modified to emit events
- Auto-exclusion: `source="pulse"` skipped
- Dedup via existing `PulseStore` ID uniqueness
- All existing tests must pass without changes
- Core (`apoch/core/`) must NOT import from `modules/` or `public_api/`

### Implementation Order (Recommended)

Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

Each phase is gated by the previous. Within Phase 3, task order is 3.1 → 3.2 → 3.3 → 3.4. Phase 4 tasks (4.1, 4.2, 4.3) are ordered and the Manager wiring (4.3) must come last as it ties everything together.
