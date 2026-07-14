# Tool Runtime Specification

## Purpose

Define the MCP tool dispatch layer: validates JSON Schema, resolves handler methods, dispatches sync/async calls, and returns structured responses. The runtime is owned by the Adapter — modules only implement handlers.

## Requirements

### Requirement: Schema Validation Before Dispatch

The runtime MUST validate incoming kwargs against the registered ToolDef.input_schema before invoking any handler. Validation MUST use the JSON Schema spec-draft.

#### Scenario: Valid kwargs pass schema validation

- GIVEN a tool with input_schema requiring `{"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}`
- WHEN kwargs `{"name": "chronicle"}` are submitted
- THEN validation MUST pass
- AND the handler MUST be invoked

#### Scenario: Invalid kwargs are rejected with VALIDATION_ERROR

- GIVEN a tool with input_schema requiring a `name` string
- WHEN kwargs `{}` are submitted
- THEN validation MUST fail
- AND the response MUST contain error code `VALIDATION_ERROR`
- AND the handler MUST NOT be invoked

### Requirement: Handler Resolution at Registration

The runtime MUST resolve `handler_name` at registration time, not on first call. The handler MUST be a public method on the module instance (no `_`-prefixed names, no arbitrary callables).

#### Scenario: Valid handler_name resolves on registration

- GIVEN a ToolDef with `handler_name="module_state"` targeting a VisionModule instance that has `module_state()` as a public method
- WHEN `register_module_tools()` is called
- THEN the tool MUST be registered successfully

#### Scenario: Non-existent handler_name fails registration

- GIVEN a ToolDef with `handler_name="nonexistent_method"` on a valid module
- WHEN `register_module_tools()` is called
- THEN registration MUST raise or log `HANDLER_NOT_FOUND`
- AND the tool MUST NOT be registered

#### Scenario: Private handler_name is rejected

- GIVEN a ToolDef with `handler_name="_private_method"` on a valid module
- WHEN `register_module_tools()` is called
- THEN registration MUST fail with `HANDLER_NOT_FOUND`

### Requirement: Sync/Async Transparent Dispatch

The runtime MUST support both sync and async handlers transparently. Dispatch MUST use `inspect.isawaitable()` on the return value — if awaitable, `await` it; otherwise return the value directly.

#### Scenario: Sync handler returns directly

- GIVEN a sync handler `def get_config(self) -> dict` that returns `{"key": "val"}`
- WHEN the handler is invoked
- THEN the runtime MUST return `{"key": "val"}` without awaiting

#### Scenario: Async handler is awaited

- GIVEN an async handler `async def get_state(self) -> dict` that returns `{"state": "running"}`
- WHEN the handler is invoked
- THEN the runtime MUST await the coroutine and return `{"state": "running"}`

### Requirement: Structured Response Format

Every tool call MUST return a structured response with version, success flag, and data or error.

#### Scenario: Successful tool call

- GIVEN a handler that returns `{"result": 42}`
- WHEN the tool is dispatched successfully
- THEN the response MUST be `{"version": 1, "ok": true, "data": {"result": 42}}`

#### Scenario: Tool execution fails

- GIVEN a handler that raises `ValueError("invalid input")`
- WHEN the tool is dispatched
- THEN the response MUST be `{"version": 1, "ok": false, "error": {"code": "MODULE_ERROR", "message": "ValueError: invalid input", "details": {"traceback": "..."}}}`
- AND the `details` field SHOULD contain the traceback

### Requirement: Error Codes

| Code | Trigger |
|------|---------|
| `VALIDATION_ERROR` | kwargs fail JSON Schema validation |
| `TOOL_NOT_FOUND` | Tool name not registered |
| `HANDLER_NOT_FOUND` | handler_name method missing or not public |
| `MODULE_ERROR` | Handler raised an exception |
| `INTERNAL_ERROR` | Unexpected runtime failure |

### Requirement: Unknown Tool Returns TOOL_NOT_FOUND

- GIVEN a tool name that is not registered
- WHEN an agent calls that tool
- THEN the response MUST contain error code `TOOL_NOT_FOUND`
