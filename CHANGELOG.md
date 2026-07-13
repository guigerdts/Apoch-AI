# Changelog

All notable changes to Apoch-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
