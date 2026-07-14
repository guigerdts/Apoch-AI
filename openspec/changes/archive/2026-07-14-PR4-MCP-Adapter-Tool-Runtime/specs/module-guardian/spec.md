# Delta for Module: Guardian

## ADDED Requirements

### Requirement: get_tool_defs for Guardian

Guardian MUST implement `get_tool_defs()` returning 2 ToolDef entries with handler_name:

| Tool Name | handler_name | Description |
|-----------|-------------|-------------|
| `guardian_diagnostics` | `diagnostics` | Return diagnostics for a specific module |
| `guardian_alldiagnostics` | `all_diagnostics` | Return diagnostics snapshot for all modules |

#### Scenario: get_tool_defs returns valid ToolDefs

- GIVEN a running GuardianModule
- WHEN `get_tool_defs()` is called
- THEN it MUST return a list of 2 ToolDef entries
- AND each entry MUST have `name`, `description`, `input_schema`, `handler_name`
- AND each `handler_name` MUST match a public method on the GuardianModule instance

#### Scenario: guardian_diagnostics dispatches to GuardianModule.diagnostics

- GIVEN the MCP gateway with Guardian loaded and tools registered
- WHEN an agent calls `guardian_diagnostics` with kwargs `{"module_name": "chronicle"}`
- THEN the response MUST be `{"version": 1, "ok": true, "data": {"current_state": "RUNNING", ...}}`
- AND the data MUST come from GuardianModule.diagnostics("chronicle")

### Requirement: MCP Tool Exposure

Guardian MUST expose `guardian_diagnostics` and `guardian_alldiagnostics` as MCP tools via the Agent Adapter. Each tool MUST return structured responses.

#### Scenario: Agent queries all diagnostics via MCP

- GIVEN the MCP gateway is running with Guardian loaded
- WHEN an agent calls `guardian_alldiagnostics`
- THEN the response MUST be `{"version": 1, "ok": true, "data": {"chronicle": {...}, "vision": {...}, ...}}`
