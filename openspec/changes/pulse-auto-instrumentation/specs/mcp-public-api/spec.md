# Delta for MCP Public API

## ADDED Requirements

### Requirement: Coordinator Emits Tool Events

The ApochCoordinator MUST emit `tool.invocation`, `tool.completed`, and `tool.error` events via EventBus so Pulse can measure tool usage transparently.

#### Scenario: Tool invocation event emitted

- GIVEN the ApochCoordinator has an `event_bus` reference
- WHEN any public tool method is called (e.g. `status`, `history`, `health`)
- THEN the Coordinator MUST emit a `TOOL_INVOCATION` event before processing begins
- AND `source` MUST be `"coordinator"`
- AND `payload` MUST include at least `{"tool": "<method_name>"}`

#### Scenario: Tool completed event emitted

- GIVEN a tool method completes successfully
- WHEN a response dict is returned
- THEN the Coordinator MUST emit `TOOL_COMPLETED` with the tool name in payload
- AND the event MUST be emitted after the response is built but before `return`

#### Scenario: Tool error event emitted

- GIVEN a tool method returns an error response
- WHEN any error response is built via `_build_error_response()`
- THEN the Coordinator MUST emit `TOOL_ERROR` with the error code and tool name

#### Scenario: Event bus propagation to coordinator

- GIVEN an `AgentAdapterManager` that creates an `ApochCoordinator`
- WHEN the Manager has access to `engine.events`
- THEN it MUST pass the EventBus to `ApochCoordinator`
- AND `ApochCoordinator.__init__` MUST accept an optional `event_bus` parameter

## MODIFIED Requirements

### Requirement: ApochCoordinator Constructor

(Previously: Coordinator only accepted ServiceRegistry and optional timeouts)

#### Scenario: EventBus accepted as optional parameter

- GIVEN an `ApochCoordinator` instance
- WHEN constructed with `event_bus=EventBus()`
- THEN the event_bus MUST be stored and used for tool event emission
- WHEN constructed without `event_bus`
- THEN tool events MUST NOT be emitted (backward compatible — no crash, no emission)

#### Scenario: Existing tests pass unchanged

- GIVEN existing coordinator unit tests that construct without event_bus
- WHEN tests exercise all tool methods
- THEN all tests MUST pass without modification
- AND no KeyError or AttributeError SHALL be raised due to missing event_bus
