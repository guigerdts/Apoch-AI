# Changelog

All notable changes to Apoch-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
