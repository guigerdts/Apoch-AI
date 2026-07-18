# Changelog

All notable changes to Apoch-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.9.3-alpha] — 2026-07-18

### Removed

- **Dead Code Removal (PR-2)** — Removed unreachable `isinstance(diag, dict): continue` guard from `RecommendationEngine._apply_health()` in `src/apoch/modules/oracle/engine.py`. This condition could never be False because every value in the health dict is always a dict from Guardian diagnostics. Zero behavioral change, zero API/contract impact, no regressions.

## [0.9.2-alpha] — 2026-07-18

### Added

- **Pulse Auto-Instrumentation (PR-1)** — Transparent instrumentation layer that captures system events as Pulse measurements without modifying existing modules (`changes/pulse-auto-instrumentation/`):
  - **EventTopics**: 8 canonical constants (`ENGINE_STARTED`, `ENGINE_STOPPING`, `MODULE_STARTED`, `MODULE_STOPPED`, `MODULE_FAILED`, `TOOL_INVOCATION`, `TOOL_COMPLETED`, `TOOL_ERROR`) replacing free strings
  - **SystemEvent**: Frozen dataclass (`event_id`, `topic`, `source`, `timestamp`, `payload`) for structured event representation
  - **EventBus → Context**: `EventBus` is passed to every module via `Context.event_bus` during engine startup, NOT via ServiceRegistry
  - **PulseEventSubscriber**: Standalone class that subscribes to EventBus topics and records measurements via PulseModule, with handler registry dict pattern (no if/elif chains)
  - **Auto-emission in all 7 tools**: Coordinator tools (`status`, `health`, `history`, `recommend`, `progress`, `insights`, `logs`) automatically emit `TOOL_INVOCATION`, `TOOL_COMPLETED`, `TOOL_ERROR` via `_auto_emit_tool_events` decorator
  - **Engine lifecycle events**: Engine emits `MODULE_STARTED`, `MODULE_STOPPED`, `MODULE_FAILED` automatically after `start_all()` / `stop_all()`
  - **Auto-exclusion**: Events from `source="pulse"` are skipped (feedback loop prevention)
  - **Backward compatibility**: Zero existing modules modified to emit events; all tests pass unchanged
  - ADR-008 documents all architecture decisions
  - 71 new tests (unit + integration)

### Changed

- `src/apoch/core/events.py` added `EventTopics`, `SystemEvent`, and `__all__` exports
- `src/apoch/core/engine.py` sets `context.event_bus` before `start_all()`; emits module lifecycle events
- `src/apoch/core/module.py` added `event_bus` field to `Context`
- `src/apoch/modules/pulse/__init__.py` exports `PulseEventSubscriber`
- `src/apoch/adapters/manager.py` wires `PulseEventSubscriber` and passes `event_bus` to coordinator

## [0.9.1-alpha] — 2026-07-17

### Fixed

- **BUG-001: Error double-wrapping in MCP dispatch** — `_dispatch()` now inspects the handler's return value. If the handler returned an error dict (`ok: False`), the error is propagated directly instead of being wrapped in a success envelope. Clients no longer need to check nested `data.ok`. (`server.py:_dispatch()`)
- **BUG-002: `healthy` field in `apoch_health`** — `health()` now computes and returns `healthy: true` or `healthy: false` depending on whether critical problems exist. Previously the field was absent. (`coordinator.py:health()`)
- **BUG-003: Empty parentheses in history summary** — When no event types matched the tracked categories (`lifecycle`, `tool`, `error`), the summary displayed empty `()`. Now parentheses are omitted when `counts_str` is empty. (`coordinator.py:history()`)
- **BUG-005: `VALIDATION_ERROR` not in error catalog** — Schema validation errors in the dispatch layer now use `ERR_INVALID_ARGUMENT` instead of the undocumented `VALIDATION_ERROR`. (`server.py:_dispatch()`)

### Changed

- `pyproject.toml` version bumped from `0.9.0-alpha` to `0.9.1-alpha`
- `src/apoch/__init__.py.__version__` bumped to `0.9.1-alpha`

- **BUG-008: MCP entry in opencode.json missing `enabled: true`** — `merge()` now writes `"enabled": true` in the Apoch-AI MCP server entry. Without it, OpenCode did not show the server as active after installation, even though it worked. Affects every user who runs `apoch install`. (`config.py:merge()`)

### UX Improvements

- `apoch mcp --help` now displays a description: "Manage the MCP gateway lifecycle: start, stop, serve, restart."
- `apoch doctor` error message for unstarted gateway now suggests the command to run: `"gateway not started — run 'apoch mcp start' or 'apoch mcp serve'"`

### Documentation

- `README.md` quick-start now explains each `apoch stack` command step
- `docs/mcp-public-api.md` error response format corrected to `{version, ok, error}` envelope
- `docs/mcp-public-api.md` `apoch_health` examples now include `healthy` field
- Error catalog documents `ERR_INVALID_ARGUMENT` usage for validation errors

---

## [0.9.0-alpha] — 2026-07-17

### Added

- **MCP Public API — 7 Intentional Tools** (`public_api/coordinator.py`): Complete redesign from module-exposed tools to a coordinated public API layer:
  - `apoch_status` — system overview aggregated from Vision, Guardian, Chronicle, Oracle
  - `apoch_health` — diagnostics from Guardian with optional Vision enrichment
  - `apoch_history` — activity timeline from Chronicle with horas/tipo filters
  - `apoch_recommend` — recommendation engine with Oracle + Guardian fallback
  - `apoch_progress` — productivity trends from Pulse with periodo enum
  - `apoch_insights` — pattern detection from Optimizer with Pulse degradation
  - `apoch_logs` — debug log entries from Vision with nivel/limite/modulo filters
- **ToolResponse Contract** (`public_api/models.py`): Standardized response format with `EvidenceSource`, `RecommendResponse` (with priority), and `ErrorResponse` across all tools
- **Error Catalog** (`public_api/errors.py`): 9 standard error codes with `error_response()` builder
- **Progressive Registration**: Each PR registers exactly its tool — no stubs, no fakes (PR2→PR8)
- **Legacy Aliases** (PR9): 5 backward-compatible wrappers (`vision_state→apoch_status`, `chronicle_query→apoch_history`, `guardian_diagnostics→apoch_health`, `guardian_all_diagnostics→apoch_health`, `vision_logs→apoch_logs`) with deprecation metadata
- **Documentation PR10**: Comprehensive MCP Public API reference (docs/mcp-public-api.md, 1,374 lines), benchmarks (docs/benchmarks.md), updated README, architecture, quickstart, and FAQ

### Changed

- `pyproject.toml` version bumped from `0.7.0-alpha` to `0.9.0-alpha`
- Module-level `get_tool_defs()` removed from Vision, Chronicle, Guardian — tools now register centrally via the coordinator
- All 11 registered tools (7 public + 5 legacy aliases minus 1 duplicate) managed by `AgentAdapterManager` in progressive order: coordinator → legacy → modules

### Fixed

- `progress()` method had orphaned continuation code from legacy alias insertion — happy-path body was split from its method. Restored and fixed `confidence` reference in no-data return path.

### Documentation

- New [MCP Public API Reference](docs/mcp-public-api.md) — complete tool docs with parameters, examples, error codes, migration guide
- New [Benchmarks](docs/benchmarks.md) — 1,471 tests, 92.1% coverage, per-area timing
- Updated [README.md](README.md) — 7 MCP tools table, 3-layer architecture diagram, 1,463 test count
- Updated [Architecture Overview](docs/architecture.md) — Public API layer added
- Updated [Quick Start](docs/quickstart.md) — MCP gateway usage section
- Updated [FAQ](docs/faq.md) — MCP tool questions added

---

## [0.8.0-alpha] — 2026-07-16

### Fixed (Critical Blockers)

- **Registry Key Mismatch** (`stack/registry.py`): `discover()` stored components under `ep.name` (lowercase) while `register()` and `get()` used `descriptor.name` (display case). Changed `discover()` to key by `instance.descriptor.name`. `apoch stack status` and `stack verify` now work correctly for all 4 components.
- **MCP Transport Loop** (`adapters/opencode/server.py`, `adapters/manager.py`, `cli/mcp.py`): Added `serve()` method to both `OpenCodeAdapter` and `AgentAdapterManager`, plus `apoch mcp serve` CLI command. The server now calls `FastMCP.run_stdio_async()` to actually serve MCP requests via stdio transport — previous process exited immediately after tool registration.
- **MCP Dispatch Parameter Mismatches** (`modules/chronicle/module.py`, `modules/vision/module.py`): 4 handler-vs-ToolDef property name conflicts fixed. `chronicle_record` now wraps `record()` with flat kwargs, `chronicle_query` wraps `query()` with flat kwargs. `vision_state` and `vision_config` handler params renamed from `name` to `module` to match their ToolDef schemas.
- **OpenCode Integration** (`adapters/opencode/config.py`): Three blockers fixed:
  - Config path: searches for `opencode.json` in project root instead of `.opencode/opencode.json`; fallback to `~/.config/opencode/opencode.json` instead of `~/.opencode/opencode.json`
  - Config key: writes Apoch entry under `"mcp"` instead of `"mcpServers"`, using `"command": ["apoch", "mcp", "serve"]` array format with `"type": "local"` — matching OpenCode's MCP server format
  - Trailing comma handling: added `_strip_trailing_commas()` helper to clean trailing commas before JSON parse, preventing `json.JSONDecodeError` on malformed config files

### Fixed (Inconsistencies)

- **codegraph.py tracked**: Added `src/apoch/stack/components/codegraph.py` (317 LOC) to version control
- **.gitignore**: Created with Python project defaults covering `__pycache__`, `.venv`, `.coverage`, `.codegraph/`, build artifacts, and development metadata

### Added

- E2E test suite: 41 real-tool validation tests across OpenSpec, Engram, Context7, CodeGraph
- CI/CD Matrix: `.github/workflows/ci.yml` (lint/test/e2e on Linux/macOS/Windows) and `.github/workflows/coverage.yml`
- Coverage infrastructure: pytest-cov with 80% global / 90% stack thresholds, HTML + XML reports, baseline at 91.8% global / 96.6% stack

---

## [0.7.0-alpha] — 2026-07-14

### Added

- **Agent Tool Dispatch Runtime** (`adapters/opencode/server.py`): Real tool dispatch replacing the stub handler. Full dispatch lifecycle:
  - `_dispatch()` — resolves tool by name, validates kwargs via JSON Schema, dispatches sync/async transparently, returns structured response
  - JSON Schema validation via `jsonschema.validate()` — maps `ValidationError` → VALIDATION_ERROR, `SchemaError` → INTERNAL_ERROR
  - Structured response envelope: `{"version": 1, "ok": true/false, "data": ..., "error": {"code": ..., "message": ...}}`
  - Handler contract enforced: `handler(**kwargs) -> dict | Awaitable[dict]`
  - `_create_handler()` — replaces standalone `_make_tool_handler`, creates FastMCP handler closures that route through `_dispatch`
  - `ToolExecutionError(TOOL_NOT_FOUND)` for unknown tool names

- **ChronicleModule.get_tool_defs()** (`modules/chronicle/module.py`): 3 MCP tools:
  - `chronicle_record` — record an activity event (source, event_type, details)
  - `chronicle_query` — query events with optional source/type/time/limit filters
  - `chronicle_stats` — aggregate statistics over all recorded events

- **GuardianModule.get_tool_defs()** (`modules/guardian/module.py`): 4 MCP tools:
  - `guardian_diagnostics` — diagnostics for a specific module
  - `guardian_all_diagnostics` — all tracked diagnostics snapshot
  - `guardian_clear_diagnostics` — clear single module diagnostics
  - `guardian_clear_all` — clear all diagnostics

- **Tool Execution Error Codes** (`core/exceptions.py`): `VALIDATION_ERROR`, `TOOL_NOT_FOUND`, `HANDLER_NOT_FOUND`, `MODULE_ERROR`, `INTERNAL_ERROR` — all mappable to structured error responses

- **`AgentAdapterManager`** (`adapters/manager.py`): Lifecycle coordinator bridging Engine + Adapter. Starts adapter, starts engine, discovers and registers module tools, handles stop in reverse order. Zero business logic — pure orchestration.

- **Handler Validation** (fail-fast at registration): Existence check, private-method rejection (`_` prefix), callable type check — all raised as `ToolExecutionError(HANDLER_NOT_FOUND)` before any tool is registered.

- **Dependency**: `jsonschema>=4.20` for JSON Schema validation at dispatch time.

### Architecture

- Dispatch is a plain method on `OpenCodeAdapter` — FastMCP closure only calls `self._dispatch(name, kwargs)`. Zero FastMCP leak.
- Error responses are always dicts — FastMCP expects JSON-serializable return values.
- `_ToolSlot` stores only `handler` + `schema` — no module reference stored.
- `AgentAdapterManager` does NOT import FastMCP or any concrete adapter — dependency injection from `get_adapter("opencode")`.
- `get_tool_defs()` imports `ToolDef` via lazy import in all three modules (chronicle, guardian, vision) — no eager adapter coupling.
- CLI `mcp.py` routes through `AgentAdapterManager` — no direct adapter calls outside `stop()`.

### Changed

- `AgentAdapter.register_module_tools()` signature: added `module: Any` parameter for handler resolution.
- `_MockModule` test handlers return `dict` (not `str`) to match the handler contract.

### Removed

- Standalone `_make_tool_handler()` stub — replaced by `OpenCodeAdapter._create_handler()`.

---

## [0.6.0-alpha] — 2026-07-13

### Added

- **Vision Query APIs** (`modules/vision/module.py`): MCP-exposable module introspection tools completing the PR3C vision module.
  - `module_state()` — states of all loaded modules via registry (including `not_found` for unknown)
  - `module_config()` — effective config dict for any module (including `not_found` for unknown)
  - `system_info()` — PID, platform, Python version, uptime, memory RSS via `/proc/self/status`
  - `get_tool_defs()` — 4 ToolDef entries: vision_state, vision_config, vision_logs, vision_system
  - `_read_memory_rss()` — reads `VmRSS` from `/proc/self/status` with graceful `None` fallback
  - Registry capture: `VisionModule.start()` now stores `context.registry` for module introspection (PR3C-A gap fix)
  - 6 new tests: 5 degraded query modes + 1 Chronicle integration

### Architecture

- All query APIs degrade gracefully: no registry → empty dict, unknown module → `not_found` dict
- `system_info()` uses stdlib only (`os`, `platform`, `time`, `/proc/self/status`) — zero external deps
- `get_tool_defs()` imports `ToolDef` via lazy import — no eager adapter coupling

---

## [0.5.0-alpha] — 2026-07-13

### Added

- **Vision Module Foundation** (`modules/vision/`): Structured NDJSON logging with rotation, ring buffer, and optional Chronicle event archival via duck-typed service injection.
  - `VisionModule(Module)` with full lifecycle (LOADED → RUNNING → STOPPED → SHUTDOWN)
  - `log()` method with NDJSON rotating file handler, in-memory ring buffer, and FATAL flush
  - `LogRecord` and `SystemInfo` data models (`modules/vision/models.py`)
  - Degraded mode: works without log directory, without Chronicle, or with failing event_sink
  - `@property services` on ChronicleModule exposing `"chronicle.record"` service contract
  - Service gathering + collision detection in `Registry.start_all()`
  - `Context.services` and `Context.registry` fields (generic, zero module names in Core)
  - 9 new tests (5 service gathering + 4 degraded mode)

### Architecture

- Core remains import-free of `modules/` — services are duck-typed via `context.services.get()`
- `context.services` is immutable at runtime — populated once, never modified
- Service key collision raises `ModuleLoadError` (fail fast, no silent overwrite)
- No circular dependencies (TYPE_CHECKING guard for ModuleRegistry in module.py)

---

## [0.4.0-alpha] — 2026-07-13

### Added

- **Guardian Module** (`modules/guardian/`): Exception isolation boundary for module lifecycle. Wraps `start()`/`stop()`/`shutdown()` calls with structured error capture.
  - `GuardianModule.protect()` with `CancelledError`/`KeyboardInterrupt` propagation
  - `ModuleDiagnostics` frozen dataclass capturing error type, message, traceback, fail count, and timestamp
  - Duck-typed integration into `ModuleRegistry` — Core remains import-free of `modules/`
  - 25 tests: diagnostics, protect success/failure, lifecycle delegation, API edge cases

### Architecture

- Guardian does NOT protect itself (raw try/except for its own lifecycle)
- Engine remains completely decoupled — zero references to any module name
- No circular dependencies between modules (Chronicle ← Guardian: no cross-imports)
- Core imports zero module code — only apoch.core.* and stdlib

---

## [0.3.0-alpha] — 2026-07-13

### Added

- **Chronicle Module** (`modules/chronicle/`): Activity recording and event timeline powered by SQLite with WAL mode.
  - `SqliteEventStore` with schema migration support, dynamic filter queries (type, source, severity, time range), and configurable auto-prune
  - `ActivityEvent`, `EventFilter`, `EventStats` data models with JSON serialization
  - `ChronicleModule(Module)` with full lifecycle: connects DB on init, starts event loop, prunes on startup
  - 35 tests (22 storage + 13 module), ~90% coverage
  - Entry point registered, `user_data_dir()` detection via `_compat.py`

---

## [0.2.0-alpha] — 2026-07-13

### Added

- **AgentAdapter ABC** (`adapters/base.py`): Abstract base class for all AI agent connectors. Defines `start()`, `stop()`, `health()`, `register_module_tools()` contract with `HealthStatus` and `ToolDef` data types. Zero dependencies beyond stdlib.

- **OpenCode Adapter** (`adapters/opencode/`): Concrete implementation of AgentAdapter wrapping a FastMCP stdio gateway. Supports idempotent start/stop, per-module tool registration with automatic duplicate prefixing, and health checks.

- **opencode.json Manager** (`adapters/opencode/config.py`): Atomic configuration reader/writer with backup/rollback, JSONC comment preservation, and schema validation. Uses `tempfile.mkstemp` + `os.replace` for crash-safe writes.

- **Adapter Registry** (`adapters/registry.py`): Central registry for discovering and resolving adapters by name. Supports entry-point-based plugin loading for third-party adapters. `OpenCodeAdapter` is registered as the built-in default.

- **CLI Commands**:
  - `apoch install` — Install Apoch-AI into OpenCode config with backup, diff display, and consent prompt
  - `apoch uninstall` — Restore opencode.json from the most recent backup
  - `apoch mcp {start|stop|restart}` — Manage the MCP gateway lifecycle
  - `apoch doctor` — Run diagnostics on all registered adapters (future-proof via `registry.list_adapters()`)

- **OpenCodeConfigError** (`core/exceptions.py`): Domain exception for opencode.json I/O errors. Extends `ApochError`.

- **Integration Tests**: 14 end-to-end tests covering the full CLI → Registry → Adapter → Config chain, including consent flow, idempotence, rollback, and MCP lifecycle.

### Architecture

- Core remains fully agnostic of adapters (zero imports from `adapters/`)
- FastMCP is encapsulated within `adapters/opencode/` (the ONLY package importing it)
- CLI never imports `OpenCodeConfig` directly — delegates through the adapter
- Constructor injection for `Engine`, `ModuleRegistry`, `OpenCodeConfig`, `OpenCodeAdapter`
- No circular imports, no singleton patterns, no hidden dependencies

---

## [0.1.0] — 2026-07-12

### Added

- **Core Engine** (`core/engine.py`, `core/events.py`, `core/module.py`, `core/registry.py`): Event-driven module system with lifecycle management (LOADED → RUNNING → STOPPED → SHUTDOWN), typed event bus, and discovery-based module loading.

- **Configuration System** (`config/loader.py`, `config/defaults.py`): Layered config via defaults → YAML file → env vars, with deep merging and unknown-key warnings.

- **Domain Exceptions** (`core/exceptions.py`): Structured exception hierarchy (`ApochError` → `ModuleLoadError`, `LifecycleError`, `StateTransitionError`, `ConfigError`, `StorageError`).

- **CLI Skeleton** (`cli/app.py`, `cli/list.py`, `cli/status.py`, `cli/output.py`): Auto-discovering typer application with `apoch list`, `apoch status`, and structured output formatting (text/JSON/verbose).

- **Test Suite**: 150 tests covering core engine, events, modules, registry, config, CLI, and exceptions.

### Architecture

- Clean Architecture: Core is dependency-free (no frameworks, no agent-specific code)
- CLI is a thin presentation layer — delegates to Engine/Registry
- Constructor injection for all major components
- Auto-discovery for both CLI subcommands and modules
