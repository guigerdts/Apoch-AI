# Module: Vision Specification

## Objective

Provide observability into Apoch-AI's internals for AI agents and developers alike — structured logging, context inspection, and module introspection through MCP-exposed tools.

## Responsibilities

- Provide structured logging with severity levels and structured payloads
- Expose module state and configuration for inspection via MCP tools
- Record and expose system resource information (process health, uptime, memory)
- Enable agents to inspect Apoch-AI's own state and diagnose issues
- Maintain a per-session context log that is queryable by agents

## Scope

### In Scope
- Structured logging with levels: DEBUG, INFO, WARN, ERROR, FATAL
- JSON-formatted log records (machine-parseable)
- MCP tool: `vision.state` — returns current module states and gateway health
- MCP tool: `vision.config` — returns effective config for a module or all modules
- MCP tool: `vision.logs` — query and return recent log entries
- MCP tool: `vision.system` — process-level health (PID, uptime, memory RSS, Python version)
- Log rotation: file-based log rotation with configurable size and count
- Integration with Chronicle for long-term event archival

### Out of Scope
- Grafana/Datadog integration (v1.1+)
- Distributed tracing
- APM-style performance metrics (v1.1+)
- Real-time log streaming to external sinks

## Architecture

Vision is a thin observability layer that sits alongside the Core. It receives structured log records from all modules and the Core itself, writing them to rotating log files and exposing them through MCP tools.

```
Module A ──log()──┐
Module B ──log()──┼──→ Vision ──→ file (rotating JSON logs)
Module C ──log()──┘       │
                           ├── MCP: vision.state
                           ├── MCP: vision.config
                           ├── MCP: vision.logs
                           └── MCP: vision.system
```

Vision does NOT own the log data long-term — Chronicle does. Vision provides the live window (last N entries) plus the MCP interface to query them.

## Public Interfaces

### Vision API

```python
class Vision:
    def log(self, level: LogLevel, message: str, *, module: str | None = None, **context) -> None: ...
    async def recent(self, limit: int = 50, level: LogLevel | None = None) -> list[LogRecord]: ...
    async def module_state(self, name: str | None = None) -> dict: ...
    async def module_config(self, name: str | None = None) -> dict: ...
    async def system_info(self) -> SystemInfo: ...
```

### Log Record Schema

```python
@dataclass
class LogRecord:
    timestamp: datetime
    level: LogLevel
    message: str
    module: str | None
    context: dict
    pid: int
```

### MCP Tools

- `vision.state` → JSON with all module states and health status
- `vision.config(module?)` → effective config for one or all modules
- `vision.logs(level?, limit?, module?)` → recent structured log entries
- `vision.system` → process and environment info

## Dependencies

- **Internal**: Guardian (state access), ConfigManager (config access), Chronicle (long-term event archival)
- **External**: Python stdlib `logging` (rotating file handler), `json`, `platform`, `psutil` or direct `/proc/self/status` parsing

## Requirements

### Requirement: Structured Logging

Vision MUST accept structured log records from any module and persist them to rotating JSON log files.

#### Scenario: Module logs at INFO level with context

- GIVEN a module that calls `vision.log(INFO, "started", module="chronicle", version="0.1.0")`
- WHEN the log is written
- THEN the log file MUST contain a JSON line with `timestamp`, `level: "INFO"`, `message: "started"`, `module: "chronicle"`, and `context.version: "0.1.0"`
- AND the file MUST be valid newline-delimited JSON

#### Scenario: Log rotation

- GIVEN a configured max log file size of 1 MB and max 3 backup files
- WHEN log entries exceed 1 MB
- THEN the log file MUST be rotated
- AND at most 3 rotated backup files MUST exist

#### Scenario: Module logs at FATAL level

- GIVEN a module that calls `vision.log(FATAL, "unrecoverable error", module="guardian")`
- WHEN the log is written
- THEN the entry MUST be persisted with level `FATAL`
- AND the entry MUST be immediately flush()'d to disk
- AND `vision.logs(level="FATAL")` MUST return the entry

### Requirement: MCP Tools for State Inspection

Vision MUST expose agent-accessible MCP tools that return the current internal state of Apoch-AI.

#### Scenario: Query module state via MCP

- GIVEN the MCP gateway is running with Vision loaded
- WHEN an agent calls `tools/call` with name `vision_state`
- THEN the response MUST include a JSON object mapping each module name to its current state (running, stopped, failed)
- AND the response MUST include gateway health status

#### Scenario: Query logs via MCP with filters

- GIVEN 100 log entries across modules, 10 of which are ERROR level from Guardian
- WHEN an agent calls `vision_logs` with `{"level": "ERROR", "module": "guardian", "limit": 5}`
- THEN the response MUST contain at most 5 entries
- AND each entry MUST have `level: "ERROR"` and `module: "guardian"`

#### Scenario: Query system info via MCP

- GIVEN the MCP gateway is running
- WHEN an agent calls `tools/call` with name `vision_system`
- THEN the response MUST include `python_version`, `platform`, `pid`, `uptime_seconds`, and `memory_rss_mb`

### Requirement: Module Configuration Inspection

Vision MUST expose the effective configuration of any loaded module.

#### Scenario: Inspect single module config

- GIVEN Chronicle is loaded with config `{"retention_days": 30}`
- WHEN an agent calls `vision_config` with `{"module": "chronicle"}`
- THEN the response MUST contain the effective Chronicle config as a JSON object

#### Scenario: Inspect config for unknown module

- GIVEN a module name that is not loaded
- WHEN an agent calls `vision_config` with `{"module": "nonexistent"}`
- THEN the response MUST indicate the module was not found with an error field

## Error Cases

| Condition | Behavior |
|-----------|----------|
| Log directory not writable | Log to stderr; warn via stderr; Vision continues degraded |
| JSON serialization failure for log context | Skip the problematic key; log warning; other context keys preserved |
| Log file rotation fails (disk full) | Fall back to single log file; emit stderr warning |
| MCP query for module state on unloaded module | Return empty state with `not_found: true`; do not error |

## Acceptance Criteria

- [ ] `vision.log()` writes valid NDJSON to rotating log file
- [ ] Log file rotates at configured size boundary without data loss
- [ ] `vision_state` MCP tool returns all module states and gateway health
- [ ] `vision_logs` MCP tool filters correctly by level, module, and limit
- [ ] `vision_system` MCP tool returns accurate PID, uptime, and Python version
- [ ] `vision_config` MCP tool returns config for loaded modules; indicates not-found for unknown modules
- [ ] Vision continues degrading gracefully when log directory is unwritable
- [ ] All events logged through Vision are routed to Chronicle for permanent storage

## Risks

| Risk | Mitigation |
|------|------------|
| Log file fills disk partition | Configurable max log size + rotation count; hard limit on total log storage |
| MCP tool output exposes sensitive config values | Policy-defined redaction for sensitive config keys (passwords, tokens) |
| High-frequency logging impacts performance | Async log writes; agent-facing queries are bounded (last N entries) |

## Future Considerations

- Structured log viewer in TUI module
- Remote log shipping (syslog, Loki, DataDog)
- Metrics collection and histogram export (Prometheus)
- Performance tracing with span IDs for cross-module operations
- Sensitive config value redaction policy
