# Delta for Module System

## ADDED Requirements

### Requirement: EventTopics Constants

Event topic strings MUST be defined as class constants in `apoch/core/events.py` to eliminate free-string typos and enable IDE autocompletion.

| Constant | Value |
|----------|-------|
| `ENGINE_STARTED` | `engine.started` |
| `ENGINE_STOPPING` | `engine.stopping` |
| `MODULE_STARTED` | `module.started` |
| `MODULE_STOPPED` | `module.stopped` |
| `MODULE_FAILED` | `module.failed` |
| `TOOL_INVOCATION` | `tool.invocation` |
| `TOOL_COMPLETED` | `tool.completed` |
| `TOOL_ERROR` | `tool.error` |

#### Scenario: Constants replace free strings

- GIVEN `EventTopics` is defined in `events.py`
- WHEN any emit call uses a topic
- THEN it MUST reference `EventTopics.CONSTANT` — never a raw string

### Requirement: EventBus in Context

The `Context` dataclass MUST include an `event_bus` field so modules can subscribe during `start()`.

#### Scenario: EventBus available during module start

- GIVEN an Engine with an `EventBus` instance
- WHEN `Engine.start()` creates `Context`
- THEN `Context.event_bus` MUST be set to the Engine's `EventBus` before `start_all()` is called
- AND any module's `start()` MUST be able to access `context.event_bus` to subscribe

### Requirement: Engine Emits Module Lifecycle Events

The Engine MUST emit `module.started`, `module.stopped`, and `module.failed` events for each module during lifecycle transitions.

#### Scenario: Module started after start_all

- GIVEN an Engine with loaded modules
- WHEN `ModuleRegistry.start_all()` completes
- THEN for each module in `RUNNING` state, Engine MUST emit `EventTopics.MODULE_STARTED` with `source` set to the module name

#### Scenario: Module stopped after stop_all

- GIVEN running modules
- WHEN `Engine.stop()` calls `ModuleRegistry.stop_all()`
- THEN for each stopped module, Engine MUST emit `EventTopics.MODULE_STOPPED`

#### Scenario: Module failure event

- GIVEN a module whose `start()` raises
- WHEN the exception is caught by Guardian boundary
- THEN after `start_all()` completes, Engine MUST emit `EventTopics.MODULE_FAILED` for each module in `FAILED` state
