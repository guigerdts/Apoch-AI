## Exploration: Apoch-AI Base Architecture

### Current State

Greenfield project. No Python code exists yet. The README contains a comprehensive project master document defining philosophy, rules, roadmap, and module inventory. OpenSpec is initialized (`openspec/config.yaml`), Engram is active, and the skill registry is populated. Six core modules are defined: Chronicle, Oracle, Guardian, Vision, Pulse, and Optimizer. The target agent for v1 is OpenCode; the architecture must remain agent-agnostic.

Project rules constrain every architectural decision:
- **Rule 001**: Never modify OpenCode source code
- **Rule 005**: Core must never depend on modules
- **Rule 006**: Modules must be installable independently
- **Rule 007**: Integrations must be reversible
- **Rule 010**: Never duplicate functionality already provided by OpenCode

### Affected Areas

- `openspec/changes/{change-name}/` — target exploration output
- `pyproject.toml` (to be created) — project metadata, dependencies, entry points
- `src/apoch/` (to be created) — core framework package
- `src/apoch/adapters/opencode/` (to be created) — OpenCode MCP integration
- `openspec/specs/foundation/` (to be created in later phases) — architecture specs

### Approaches

---

#### 1. Core Engine — Event-Driven vs Direct Lifecycle Hooks

**1A. Event-Driven Pub/Sub Core**
- How it works: Core exposes an event bus. Modules subscribe to lifecycle events (init, start, stop, shutdown). The bus dispatches events; modules react asynchronously.
- Pros: Maximum loose coupling; modules can react to events from other modules without direct imports; natural fit for Python's `asyncio`; easy to add instrumentation and logging
- Cons: Harder to trace execution flow; async error handling is more complex; requires a robust event contract; more indirection for simple scenarios
- Effort: Medium

**1B. Direct Lifecycle Hooks (Template Method)**
- How it works: Core calls `module.init(config)`, `module.start(ctx)`, `module.stop()`, `module.shutdown()` in sequence. Each module implements these methods from an ABC.
- Pros: Simple, predictable, easy to debug and trace; explicit ordering guarantees; no event dispatch overhead; familiar pattern (similar to FastAPI lifespan, Django AppConfig)
- Cons: Tighter coupling between core and modules; synchronous by nature; harder for modules to observe each other's state without direct imports
- Effort: Low

**RECOMMENDATION: 1B (Direct Lifecycle Hooks) with an optional event bus**

Start with direct hooks for the core lifecycle — it is simpler, more predictable, and sufficient for v1. Add an optional event bus layer (wrapping `asyncio.Event` / custom dispatcher) **inside the core** for inter-module communication when needed. The bus should be a core service, not a module dependency. This satisfies Rule 005 (core does not depend on modules) while providing an escape hatch for future complexity.

---

#### 2. Module System — Entry Point Discovery vs Configuration-Based

**2A. Python Entry Point Discovery (`importlib.metadata`)**
- How it works: Modules declare themselves via `[project.entry-points."apoch.modules"]` in `pyproject.toml`. Core scans entry points at startup. Each module is a Python package with a known factory function.
- Pros: Zero-config discovery; pip-installed modules are automatically found; Python-idiomatic (same pattern as pytest plugins, uvicorn workers); enables independent module installation (Rule 006); supports namespace packages
- Cons: Requires `pyproject.toml` modification for local modules; entry points are process-wide (can conflict); implicit activation — user may not know what's loaded
- Effort: Low

**2B. Configuration-Based Registry (YAML/TOML manifest)**
- How it works: Modules listed in `apoch.yaml` or `apoch.toml` under a `modules:` section. Core reads the config file, imports each module by dotted path, and loads it.
- Pros: Explicit and transparent; user controls what loads and in what order; easy to toggle modules on/off; no packaging needed for local modules; simple to implement
- Cons: Manual registration; pip-installed modules don't auto-register; config file can get out of sync; more friction for third-party modules
- Effort: Low

**RECOMMENDATION: 2A (Entry Point Discovery) + 2B (Configuration Override)**

Use entry points as the **primary discovery mechanism** — this is what makes modules pip-installable and auto-discoverable (Rule 006). Supplement with a config file that allows:
- Disabling discovered modules
- Loading non-packaged modules by path (for development)
- Setting module-specific options

This hybrid gives the best of both: zero-config for standard modules, explicit control when needed.

---

#### 3. Plugin System — Extending the Module Interface

**3A. Entry Point-Based Plugins (Same as Modules)**
- How it works: Third-party plugins use the same entry point mechanism as first-party modules. They implement the same `Module` ABC and lifecycle. Version compatibility is declared in `pyproject.toml` via `requires-python` and dependency pins.
- Pros: No separate plugin API or discovery mechanism; module == plugin (one concept); immediate familiarity; pip install works; minimal code
- Cons: No version negotiation beyond pip resolution; no plugin marketplace/registry; compatible breaking changes require manual coordination; no sandboxing
- Effort: Low

**3B. Separate Plugin Registry with Version Constraints**
- How it works: A dedicated `PluginManager` reads from a local registry (`~/.apoch/plugins.yaml`) or remote index. Plugins declare `apoch-version` constraints in their metadata. The manager validates compatibility before activation. Supports `enabled`/`disabled` state, dependency resolution, and conflict detection.
- Pros: Explicit version management; can support a plugin marketplace; enables disable/revert without uninstalling; can warn about incompatible plugins before loading
- Cons: More code to write and maintain; adds another concept (module vs plugin distinction adds cognitive load); remote index needs infrastructure; over-engineered for v1
- Effort: High

**RECOMMENDATION: 3A (Entry Point-Based) for v1, defer 3B**

For v1, plugins ARE modules — same ABC, same lifecycle, same discovery. The entry point mechanism gives third-party developers everything they need. Revisit 3B when:
- A community emerges and needs version negotiation
- Plugin conflict resolution becomes a real problem
- A plugin marketplace is desired

---

#### 4. Agent Adapter (OpenCode Integration) — MCP Server Strategy

**4A. Single Gateway MCP Server**
- How it works: Apoch-AI runs ONE MCP server process that exposes all active modules' tools. The server uses stdio transport. `opencode.json` has one entry: `"apoch": { "type": "local", "command": ["apoch", "mcp"] }`.
- Pros: Single config entry; unified lifecycle management; shared state across modules in one process; simpler to install and uninstall; easier to configure auth/timeout once
- Cons: Single point of failure; all modules share one process (memory, crash domain); module isolation is logical only; tool namespace collisions need manual resolution
- Effort: Medium

**4B. Per-Module Independent MCP Servers**
- How it works: Each module runs as its own independent MCP server. `opencode.json` has one entry per module. Each tool namespace is naturally separated by server name. Modules can be independently enabled/disabled via OpenCode's tool permissions.
- Pros: Maximum isolation (crash, memory, lifecycle); independent scaling; OpenCode can enable/disable per-module tools naturally; follows MCP best practice of one concern per server; "install independently" satisfied at the protocol level
- Cons: N config entries in `opencode.json` (N modules); each server adds startup overhead; more processes to manage; install/uninstall must add/remove N entries; auth/timeout configured per-server
- Effort: Medium

**RECOMMENDATION: 4A (Single Gateway) for v1, with path to 4B later**

For v1, the single gateway server is simpler to install, manage, and document. The MCP protocol itself handles routing by tool name. Design the gateway so it can be split into per-module servers later without changing the module interface — each module already implements its own tool set. The gateway is just a dispatcher. The path to 4B means: the gateway process should accept a `--modules` flag or config that specifies which modules to serve, and each module's tools should be prefixed or namespaced for future independent hosting.

This satisfies Rule 001 (no OpenCode source modification — MCP is the supported extension mechanism) and Rule 010 (no duplication — MCP tool registration is something OpenCode already does natively).

---

#### 5. Entry Point — CLI vs TUI

**5A. CLI-First with Minimal TUI**
- How it works: Primary interface is CLI commands: `apoch install`, `apoch uninstall`, `apoch list`, `apoch status`, `apoch mcp` (start MCP server), `apoch config`. Uses `rich` or `click` for polished but terminal-native output.
- Pros: Simplest to implement and test; scriptable (CI/CD); cross-platform by definition; composable (pipelines, aliases); minimal dependencies
- Cons: Less discoverable for new users; status monitoring requires terminal commands; no dashboard for module health
- Effort: Low

**5B. TUI-First (Terminal Dashboard)**
- How it works: Full TUI using `textual` or `urwid`. Dashboard shows module status, health, logs. All CLI actions available through TUI commands. MCP server management through interactive menus.
- Pros: Richer UX; live monitoring; discoverability; more "product-like" feel; status at a glance
- Cons: Much more complex to build and test; `textual` dependency is heavy; harder to script; cross-platform terminal edge cases; TUI frameworks churn
- Effort: High

**RECOMMENDATION: 5A (CLI-First), TUI as optional module**

Start with CLI using `click` (or `typer` for async support). It is the fastest path to working integration. Design the entry point as:
```
apoch install          # Install Apoch-AI and configure OpenCode integration
apoch uninstall        # Remove Apoch-AI and revert OpenCode config
apoch list             # List installed modules
apoch status           # Show module/plugin health
apoch mcp              # Start MCP server (foreground/daemon)
apoch config           # View/edit configuration
apoch module enable|disable  # Toggle modules
```

The TUI can be implemented as a module (e.g., `apoch-module-dashboard`) in a later phase, using the same CLI under the hood.

---

#### 6. Core Stack Integration

**6A. Managed via Apoch-AI Installer (Gentle-AI approach)**
- How it works: `apoch install` detects and installs/configures OpenSpec (already present), Engram (via pip/extension), Context7 (via `opencode.json` MCP entry), and CodeGraph (via pip/npm). Each is a post-install step. Installation is re-entrant and reversible (Rule 007).
- Pros: Single command setup; consistent experience; can verify each component works; can update independently; follows "installation experience like Gentle-AI" from README
- Cons: Needs detection logic for each component; platform-specific paths; must handle already-installed state; more code in the installer
- Effort: Medium

**6B. Documentation-Driven (User Installs Manually)**
- How it works: README lists each component with install instructions. Apoch-AI expects them to be available and fails gracefully if not.
- Pros: Zero installer code; no detection/management logic; respects existing tools the user may already have; no risk of breaking existing config
- Cons: Poor user experience; not "simple installation" per the README goals; error messages are useless; violates "installation experience should resemble Gentle-AI"
- Effort: Low

**RECOMMENDATION: 6A (Managed via Installer) for the core stack**

The README explicitly says: "Apoch-AI installs and manages the following core integrations" — this implies active management, not passive documentation. The installer should:
1. Check if each component is already configured
2. If missing, install/configure it
3. If present, verify it works
4. Report status per component
5. Support `apoch uninstall` to revert changes

OpenSpec is already initialized. Engram is extension-level. Context7 and CodeGraph need MCP config entries in `opencode.json` (the existing `gentle-ai install` already does this — Apoch-AI should complement, not duplicate, what gentle-ai already manages).

---

#### 7. Project Structure

**7A. Flat Layout (`src/apoch/`)**
```
src/apoch/
├── __init__.py
├── __main__.py              # python -m apoch
├── cli/
│   ├── __init__.py
│   └── main.py              # Click/typer app
├── core/
│   ├── __init__.py
│   ├── engine.py            # Bootstrap and lifecycle
│   ├── module.py            # Module ABC
│   └── events.py            # Event bus
├── modules/
│   ├── __init__.py
│   ├── chronicle/
│   ├── oracle/
│   ├── guardian/
│   ├── vision/
│   ├── pulse/
│   └── optimizer/
├── adapters/
│   ├── __init__.py
│   ├── base.py              # Agent adapter ABC
│   ├── opencode/
│   │   ├── __init__.py
│   │   ├── server.py        # MCP server implementation
│   │   └── config.py        # opencode.json integration
│   └── registry.py
├── plugins/
│   ├── __init__.py
│   └── manager.py           # Plugin discovery and lifecycle
├── stack/
│   ├── __init__.py
│   ├── openspec.py
│   ├── engram.py
│   ├── context7.py
│   └── codegraph.py
└── _compat.py               # Cross-platform utilities
```

- Pros: Standard Python layout; clear separation of concerns; each domain has a home; easy to navigate
- Cons: Nested packages add import depth; `src/` layout means `pip install -e .` is required for development
- Effort: Low

**7B. Top-Level Package (Flat `apoch/`)**
```
apoch/
├── __init__.py
├── __main__.py
├── cli.py
├── core/
│   ├── __init__.py
│   ├── engine.py
│   ├── module.py
│   └── events.py
├── modules/
│   ...
├── adapters/
│   ...
└── _compat.py
```

- Pros: Simpler imports; no `src/` overhead; typical for small-to-medium projects; works without editable install
- Cons: Less standard in professional Python (PEP 517/518 recommend `src/`); harder to test against installed package; top-level namespace pollution risk
- Effort: Low

**RECOMMENDATION: 7B (Top-Level `apoch/`) with `src/`-ready structure for v1**

For v1's rapid iteration, the flat `apoch/` layout is fine. But design it so migrating to `src/apoch/` later is a mechanical move (imports are relative within the package, CI uses `pip install -e .`). Use `pyproject.toml` with `[project.scripts]` for the CLI entry point: `apoch = "apoch.cli.main:app"`.

### Recommendation Summary

| Area | Chosen Approach | Justification |
|------|----------------|---------------|
| Core Engine | Direct Lifecycle Hooks + optional event bus | Simple, predictable, sufficient for v1 |
| Module System | Entry point discovery + config override | Pythonic, zero-config, independently installable |
| Plugin System | Plugins ARE modules (entry point-based) | One concept, minimal code, defer complexity |
| OpenCode Integration | Single gateway MCP server (path to per-module) | MCP is native to OpenCode, no source modification needed, Rule 001 satisfied |
| Entry Point | CLI-first (click/typer), TUI as optional module | Fastest to ship, composable, cross-platform |
| Core Stack | Managed installer (Gentle-AI-like) | Per README: "install and manage" |
| Project Layout | Top-level `apoch/` package | Low ceremony, v1 iteration speed |

### Integration Architecture (OpenCode)

The key architectural insight from this exploration:

```
OpenCode Agent
    │
    │  MCP Protocol (stdio)
    ▼
apoch mcp  ──►  MCP Server (FastMCP / custom stdio)
    │
    ├── Core Engine (lifecycle, config, events)
    │       │
    │       ├── Module: Chronicle
    │       ├── Module: Oracle
    │       ├── Module: Guardian
    │       ├── Module: Vision
    │       ├── Module: Pulse
    │       └── Module: Optimizer
    │
    ├── Agent Adapters (opencode, future)
    │       │
    │       └── opencode/mcp_server.py
    │
    ├── Plugin Manager
    │       │
    │       └── Third-party plugins (entry points)
    │
    └── Stack Manager
            │
            ├── OpenSpec (spec-driven dev)
            ├── Engram (persistent memory)
            ├── Context7 (documentation)
            └── CodeGraph (code intelligence)
```

OpenCode never imports or modifies Apoch-AI code. Apoch-AI runs as an independent MCP server child process. OpenCode connects to it via the standard MCP protocol — the same way it connects to any other MCP server. This satisfies every project rule simultaneously:
- Rule 001: No OpenCode source modification (MCP is the intended extension mechanism)
- Rule 002: No fork (OpenCode binary is untouched)
- Rule 010: No duplication (OpenCode already handles MCP client/server protocol)

### Risks

- **MCP protocol maturity**: OpenCode's MCP implementation is evolving (V1 vs V2 config shapes differ). Pin Apoch-AI to a specific OpenCode compatibility range.
- **Per-module vs gateway**: If modules grow large or crash-prone, single-gateway architecture becomes a risk. Design the gateway for future split from day one.
- **Gentle-AI overlap**: The core stack installer may overlap with what `gentle-ai install` already does for Context7 and CodeGraph. Detect prior gentle-ai installation and defer to it rather than duplicating (Rule 010).
- **Cross-platform stdio MCP**: stdio MCP relies on child process management. On Windows, this behaves differently (no POSIX signals, different process tree). The MCP server must handle SIGTERM emulation and process cleanup portably.
- **Module isolation**: With direct lifecycle hooks in a single process, a misbehaving module can crash the entire Apoch-AI gateway. Consider per-module exception boundaries or process isolation from v1 design.

### Ready for Proposal

Yes. The exploration is comprehensive for a greenfield architecture. The orchestrator should proceed with **sdd-propose** to formalize the change proposal, using these recommendations as the basis.

Key items for the proposal phase:
- Formalize the Module ABC (methods, attributes, error contract)
- Design the MCP tool schema (how modules expose tools, resources, prompts)
- Define the installation flow (detect OpenCode, configure `opencode.json`, start MCP server)
- Define the event bus contract (events, payloads, ordering guarantees)
- Specify the per-module exception boundary strategy
