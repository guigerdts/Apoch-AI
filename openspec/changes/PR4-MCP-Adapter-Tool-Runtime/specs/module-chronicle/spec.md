# Delta for Module: Chronicle

## ADDED Requirements

### Requirement: get_tool_defs for Chronicle

Chronicle MUST implement `get_tool_defs()` returning 2 ToolDef entries with handler_name:

| Tool Name | handler_name | Description |
|-----------|-------------|-------------|
| `chronicle_query` | `query` | Query recorded events with optional filter |
| `chronicle_stats` | `stats` | Return aggregate event statistics |

#### Scenario: get_tool_defs returns valid ToolDefs

- GIVEN a running ChronicleModule
- WHEN `get_tool_defs()` is called
- THEN it MUST return a list of 2 ToolDef entries
- AND each entry MUST have `name`, `description`, `input_schema`, and `handler_name`
- AND each `handler_name` MUST match a public method on the ChronicleModule instance

#### Scenario: chronicle_query dispatches to ChronicleModule.query

- GIVEN the MCP gateway with Chronicle loaded and tools registered
- WHEN an agent calls `chronicle_query` with kwargs `{"limit": 5}`
- THEN the response MUST be `{"version": 1, "ok": true, "data": [...]}` containing up to 5 events
- AND the data MUST come from ChronicleModule.query()

### Requirement: MCP Tool Exposure

Chronicle MUST expose `chronicle_query` and `chronicle_stats` as MCP tools via the Agent Adapter. Each tool MUST return structured responses.
(Previously referenced in spec as requirement — now explicitly wired through ToolDef.)

#### Scenario: Agent queries Chronicle stats via MCP

- GIVEN the MCP gateway is running with Chronicle loaded
- WHEN an agent calls `tools/call` with name `chronicle_stats`
- THEN the response MUST be `{"version": 1, "ok": true, "data": {"total_count": N, "by_type": {...}, "by_severity": {...}}}`
