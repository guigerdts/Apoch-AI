# Delta for Module: Vision

## MODIFIED Requirements

### Requirement: MCP Tools for State Inspection

Vision MUST expose agent-accessible MCP tools that return the current internal state of Apoch-AI. Tools MUST use the new ToolDef format with handler_name and return structured responses.
(Previously: Tools were described with stub handlers only. No structured response format defined.)

#### Scenario: Query module state via MCP

- GIVEN the MCP gateway is running with Vision loaded, and Vision's get_tool_defs() returns ToolDefs with handler_name="module_state"
- WHEN an agent calls `tools/call` with name `vision_state`
- THEN the response MUST be `{"version": 1, "ok": true, "data": {"vision": "RUNNING", "chronicle": "RUNNING"}}`

#### Scenario: Invalid args return VALIDATION_ERROR

- GIVEN an agent calls `vision_state` with invalid kwargs such as `{"module": ["not", "a", "string"]}`
- WHEN the tool is invoked
- THEN the response MUST be `{"version": 1, "ok": false, "error": {"code": "VALIDATION_ERROR", "message": "..."}}`
- AND the module_state handler MUST NOT be called
