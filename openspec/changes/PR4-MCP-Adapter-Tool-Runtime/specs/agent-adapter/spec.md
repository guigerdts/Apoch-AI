# Delta for Agent Adapter

## MODIFIED Requirements

### Requirement: Module Tool Registration

Modules MUST be able to register their tools with the adapter for MCP exposure. The gateway MUST aggregate all registered tools from all loaded modules. Tool registration wires a dispatch pipeline: schema validation, handler resolution, sync/async dispatch, structured response.
(Previously: Registration only created stub handlers that echoed kwargs. No dispatch, no validation, no structured response.)

#### Scenario: Multiple modules register tools

- GIVEN two loaded modules, each providing two tools with valid ToolDefs including handler_name
- WHEN both modules call `adapter.register_module_tools()` during initialization
- THEN the gateway MUST expose exactly four tools via MCP `tools/list`
- AND each tool MUST dispatch to its correct module method
- AND the response MUST follow the structured format `{"version": 1, "ok": true, "data": ...}`

#### Scenario: Module registers tool with non-existent handler

- GIVEN a ToolDef with handler_name pointing to a method that does not exist on the module
- WHEN `register_module_tools()` is called
- THEN the registration MUST fail with `HANDLER_NOT_FOUND`
- AND the tool MUST NOT be registered
- AND a warning MUST be logged

### Requirement: Gateway Health

(Unchanged — no modification to health check behavior.)

#### Scenario: Healthy gateway

(Unchanged — no modification.)

#### Scenario: Gateway process crashed

(Unchanged.)

#### Scenario: Gateway restart restores health

(Unchanged.)
