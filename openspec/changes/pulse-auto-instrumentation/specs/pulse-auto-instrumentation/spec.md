# Pulse Auto-Instrumentation Specification

## Purpose

Transparently capture system events via EventBus and record them as Pulse measurements without modifying any existing module. This is the data source that makes Pulse visible immediately — enabling `apoch_progress` and `apoch_insights` to return real data from day one.

## Requirements

### Requirement: SystemEvent Immutable Model

SystemEvent is the canonical event representation passed between EventBus subscribers and handlers. It MUST be a frozen dataclass.

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `str` | `uuid4.hex` — unique identifier |
| `topic` | `str` | From `EventTopics` constants |
| `source` | `str` | Module name, `"engine"`, or `"coordinator"` |
| `timestamp` | `str` | ISO 8601 UTC |
| `payload` | `dict` | Immutable after construction; context-specific data |

#### Scenario: SystemEvent immutability enforced

- GIVEN a constructed SystemEvent
- WHEN code attempts to modify any field
- THEN `dataclasses.FrozenInstanceError` MUST be raised

#### Scenario: Event with topic from EventTopics

- GIVEN a `TOOL_COMPLETED` event
- WHEN a PulseEventSubscriber handler receives it
- THEN `event.topic` MUST equal `EventTopics.TOOL_COMPLETED`
- AND `event.payload` MUST contain at least `{"tool": str}`

### Requirement: PulseEventSubscriber

A standalone class (NOT inside PulseModule) that subscribes to EventBus, transforms events to `MeasurementInput`, and calls `PulseModule.record()`. Uses a handler registry dict — never if/elif chains.

#### Scenario: Subscriber registers on start

- GIVEN an EventBus and a PulseModule reference
- WHEN `PulseEventSubscriber.start()` is called
- THEN it MUST subscribe to `TOOL_COMPLETED`, `ENGINE_STARTED`, and `ENGINE_STOPPING`
- AND handlers MUST be registered via a `dict[str, Callable]` lookup keyed by `EventTopics` constant

#### Scenario: TOOL_COMPLETED produces measurement

- GIVEN a `TOOL_COMPLETED` event with payload `{"tool": "apoch_status"}`
- WHEN the subscriber handler processes it
- THEN it MUST construct a `MeasurementInput` with a stable `work_unit_id`
- AND call `PulseModule.record()` once
- AND the measurement SHALL be persisted in PulseStore

#### Scenario: Unhandled topic is silently ignored

- GIVEN an event with topic not in the handler registry
- WHEN the subscriber receives it
- THEN it MUST NOT call `PulseModule.record()`
- AND no error SHALL be raised or logged at WARNING+ level

### Requirement: Auto-Exclusion (Feedback Loop Prevention)

Events with `source="pulse"` MUST be discarded to prevent infinite loops.

#### Scenario: Pulse-sourced events skipped

- GIVEN an event where `event.source == "pulse"`
- WHEN any handler receives it
- THEN handler MUST return immediately without calling `PulseModule.record()`

### Requirement: Backward Compatibility

No existing module MAY be modified to emit events. All instrumentation MUST be transparent.

#### Scenario: No modules modified

- GIVEN the codebase before this change
- WHEN comparing the git diff for this PR
- THEN no file under `modules/` SHALL have any functional change
- AND all existing tests SHALL pass with zero modifications

#### Scenario: Core dependency rule preserved

- GIVEN `apoch/core/` modules
- WHEN reviewing imports
- THEN core MUST NOT import from `modules/` or `public_api/`
- AND `EventTopics` and `SystemEvent` MUST be importable by core without depending on any module

### Requirement: Deduplication

Duplicate events MUST be handled gracefully — PulseStore already rejects duplicate `work_unit_id` values.

#### Scenario: Duplicate event silently handled

- GIVEN a `SystemEvent` with `event_id` already recorded as a `work_unit_id`
- WHEN the subscriber attempts to record it
- THEN `PulseModule.record()` MUST raise `StorageError` (existing behavior)
- AND the subscriber MUST catch the error and log a DEBUG message
- AND NOT propagate the exception

### Requirement: Wiring

The `AgentAdapterManager` MUST instantiate and start `PulseEventSubscriber` after the Engine and Coordinator are initialized.

#### Scenario: Subscriber started after coordinator

- GIVEN Engine is started, modules are loaded, and Coordinator is created
- WHEN `AgentAdapterManager.start()` proceeds after Coordinator creation
- THEN it MUST create `PulseEventSubscriber(event_bus, pulse_module)`
- AND call `subscriber.start()`
- AND `PulseEventSubscriber` MUST hold a reference only to `PulseModule.record()` — never to Pulse internals
