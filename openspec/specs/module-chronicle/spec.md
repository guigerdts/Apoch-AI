# Module: Chronicle Specification

## Objective

Record, store, and query significant activity within Apoch-AI — module lifecycle events, tool invocations, errors, and user actions — providing a queryable timeline for debugging, auditing, and visibility.

## Responsibilities

- Record structured activity events with timestamp, type, source, and payload
- Store events persistently across sessions
- Provide a query interface for filtering and retrieving events
- Expose MCP tools for agents to query activity history
- Support configurable retention and pruning

## Scope

### In Scope
- Activity events: module lifecycle (init, start, stop, shutdown), tool invocations, errors, warnings, user actions
- Event schema: `{id, timestamp, type, source, severity, payload}`
- Storage backend abstraction (v1: SQLite file-based storage)
- Query interface: filter by time range, event type, source module, severity
- MCP tool: `chronicle.query` for agent-facing history inspection
- MCP tool: `chronicle.stats` for aggregate event statistics
- Configurable retention period (default: 30 days) with automatic pruning

### Out of Scope
- Distributed tracing across processes
- Real-time event streaming (future)
- External log shipping (future syslog/ELK integration)
- Visualization dashboard (future module)

## Architecture

Chronicle receives events from other modules and the Core via a synchronous `record()` call. Events are serialized and stored in a SQLite database at `~/.local/share/apoch/chronicle.db`. The query layer reads from the same DB.

```
Module → Chronicle.record(event) → EventStore (SQLite)
Agent → chronicle.query()        → QueryEngine → EventStore
System → prune task (cron-like)  → EventStore (DELETE old)
```

## Public Interfaces

### Core API (internal to Apoch-AI)

```python
class Chronicle:
    async def record(self, event: ActivityEvent) -> None: ...
    async def query(self, filter: EventFilter) -> list[ActivityEvent]: ...
    async def stats(self) -> EventStats: ...
    async def prune(self, before: datetime) -> int: ...
```

### MCP Tools (exposed to agent)

- `chronicle.query(type?, source?, severity?, since?, until?, limit?)` → list of events
- `chronicle.stats` → total count, count by type, count by severity

## Dependencies

- **Internal**: Module ABC, Guardian (data integrity), Vision (diagnostic logging)
- **External**: Python stdlib `sqlite3`, `datetime`

## Requirements

### Requirement: Record Activity Events

Chronicle MUST record any event passed through `record()` and persist it durably.

#### Scenario: Record a lifecycle event

- GIVEN a `ModuleLifecycleEvent` with type `started`, source `guardian`, timestamp `now`
- WHEN `chronicle.record(event)` is called
- THEN the event MUST be written to the SQLite database
- AND `chronicle.query(type="lifecycle")` MUST include the recorded event in its results

#### Scenario: Record a tool invocation

- GIVEN a tool call event with type `tool_invocation`, source `chronicle.query`, payload containing filter parameters
- WHEN `chronicle.record(event)` is called
- THEN the event MUST be stored with all payload fields preserved

#### Scenario: Record 10,000 events in rapid succession

- GIVEN 10,000 events generated within 1 second
- WHEN `chronicle.record()` is called for each event
- THEN all 10,000 events MUST be persisted
- AND the full round-trip MUST complete within 10 seconds

### Requirement: Query Events

Chronicle MUST allow filtering of recorded events by time range, type, source, severity, and limit.

#### Scenario: Query by time range

- GIVEN events recorded across three days
- WHEN `chronicle.query(since="2026-07-10", until="2026-07-12")` is called
- THEN only events within that date range MUST be returned

#### Scenario: Query with no matching events

- GIVEN zero events of type `error`
- WHEN `chronicle.query(type="error")` is called
- THEN an empty list MUST be returned

#### Scenario: Query with limit

- GIVEN 100 recorded events
- WHEN `chronicle.query(limit=5)` is called
- THEN exactly 5 events MUST be returned
- AND they MUST be the most recent 5 events (descending time)

### Requirement: Retention and Pruning

Chronicle MUST provide automatic pruning of events older than the configured retention period.

#### Scenario: Prune old events

- GIVEN events older than the 30-day retention period
- WHEN the daily prune task runs
- THEN events older than 30 days MUST be deleted
- AND the count of deleted events MUST be logged
- AND events within the retention period MUST be preserved

#### Scenario: No events to prune

- GIVEN all events are within the retention period
- WHEN the prune task runs
- THEN no events MUST be deleted
- AND the task MUST complete successfully

### Requirement: MCP Tool Exposure

Chronicle MUST expose `chronicle.query` as an MCP tool via the Agent Adapter.

#### Scenario: Agent queries Chronicle via MCP

- GIVEN the MCP gateway is running with Chronicle loaded
- WHEN an agent calls `tools/call` with name `chronicle_query` and arguments `{"limit": 3}`
- THEN the response MUST contain a list of up to 3 events in JSON format
- AND each event MUST include `id`, `timestamp`, `type`, and `source`

## Error Cases

| Condition | Behavior |
|-----------|----------|
| SQLite disk full | `record()` raises `StorageError`; event logged via Vision; data loss is bounded to current batch |
| DB file corrupted on open | Chronicle attempts rebuild from WAL; if that fails, reset to fresh DB with archive of old file |
| Query with invalid filter (future date) | Return empty result; log warning |
| Concurrent write contention | Use WAL mode; retry up to 3 times with backoff |

## Acceptance Criteria

- [ ] `chronicle.record()` persists with < 5ms latency (p95) for typical event
- [ ] `chronicle.query()` with filters returns correct subset
- [ ] 10,000 events stored and queried without failure
- [ ] Events older than retention are removed on prune
- [ ] MCP tool `chronicle_query` returns valid JSON event list
- [ ] All events survive process restart (SQLite persistence proven)

## Risks

| Risk | Mitigation |
|------|------------|
| SQLite write contention under high throughput | Use WAL mode; batch writes if needed in v1.1 |
| DB file grows unbounded | Mandatory retention-based pruning; warn if approaching disk limit |
| Timestamp precision for high-frequency events | Use microsecond precision; monotonic clock for ordering |

## Future Considerations

- Event streaming to external systems (syslog, ELK, DataDog)
- Event bus subscription model (modules subscribe to event types)
- Indexed queries for full-text search across event payloads
- Export/import timeline for debugging and reproduction
