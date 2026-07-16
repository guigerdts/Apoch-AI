# PR8 — CodeGraph Stack Component Proposal

## Intent
Integrate CodeGraph as the fourth `apoch stack` component. Apoch does NOT implement CodeGraph — it acts as an adapter to the official project via its public CLI.

CodeGraph is a local-first code intelligence knowledge graph for AI coding agents: an npm CLI package that pre-indexes codebases into a SQLite knowledge graph with symbol resolution, call paths, blast-radius analysis, and MCP-based agent integration.

**Reference Component**: OpenSpec (PR5). CodeGraph follows the exact same structure, lifecycle, and patterns, changing only the adapter-specific logic.

## Core Stack Philosophy (MANDATORY — ALL components)
Apoch does NOT implement any component. It only acts as an adapter to each official project using its public interface. All project-specific information (install command, URLs, version detection, prerequisites) must come from the official project — never hardcoded from assumptions.

## Governance Compliance

| Rule | Status |
|------|--------|
| 1. Core Stack frozen | ✅ No modifications to StackComponent, StackDescriptor, ComponentInfo, ComponentStatus, StackManager, StackState, derive_state(), or CLI |
| 2. CliComponent deferred | ✅ KEEP CURRENT DESIGN per ADR (31.6% shared, below 60% threshold). No new abstractions. |
| 3. PRs bounded | ✅ Target ≤1200 lines per PR. Forecast: Foundation (~260) + Core (~560) = ~820 total. OK for force-chained. |
| 4. Public interfaces only | ✅ codegraph public CLI only. No internal files, undocumented endpoints, or unreleased commands. |
| 5. Reference Component Rule | ✅ OpenSpec is the reference. Any structural difference must be justified by a documented CodeGraph CLI limitation. |

## CodeGraph Public Interface (verified against official docs)

Source: https://github.com/colbymchenry/codegraph (codegraph CLI v1.4.1 — Jul 10, 2026)
License: MIT
Homepage & Docs: https://colbymchenry.github.io/codegraph/
CLI docs: https://colbymchenry.github.io/codegraph/reference/cli/
npm: https://www.npmjs.com/package/@colbymchenry/codegraph
Author: Colby McHenry (colbymchenry)

| Interface | Details | Source |
|-----------|---------|--------|
| **Homepage** | `https://colbymchenry.github.io/codegraph/` | npm registry |
| **Repository** | `https://github.com/colbymchenry/codegraph` | npm registry |
| **Docs** | `https://colbymchenry.github.io/codegraph/` | Official site |
| **CLI binary** | `codegraph <command>` — npm package (self-contained, bundles own Node.js runtime) | CLI docs |
| **npm package** | `@colbymchenry/codegraph` (latest: 1.4.1) | npm registry |
| **Version** | `codegraph --version` → bare semver (e.g., `1.3.1` — NO prefix) | Verified: `1.3.1` |
| **Install** | `npm install -g @colbymchenry/codegraph` (also: curl install.sh for no-Node setups) | CLI docs |
| **Uninstall** | `npm uninstall -g @colbymchenry/codegraph` | npm standard |
| **Doctor/Health CLI** | ❌ **NO EXISTE** — confirmed from full command reference, --help, and changelog. CodeGraph has NO doctor/diagnostic command. | CLI docs |
| **Verification substitute** | `codegraph --help` — returns exit 0 when binary responds (Context7 pattern) | Verified |
| **Health JSON substitute** | `codegraph status --json` — always returns exit 0 + valid JSON with `version` field, even in non-initialized projects. Does NOT require `.codegraph/` to exist. | Verified: `{"initialized":false,"version":"1.3.1",...}` |
| **Requirements** | Node.js (any version) — requires `npm` for the official install method | npm registry + CLI docs |
| **Privacy** | `codegraph telemetry [status\|on\|off]` — anonymous usage telemetry, opt-out by default | CLI reference |
| **License** | MIT | npm registry |

### Available CLI commands (verified)

```bash
# Project graph
codegraph init [path]               # Initialize + build graph (one step)
codegraph uninit [path]             # Remove .codegraph/ (--force to skip prompt)
codegraph index [path]              # Full re-index from scratch
codegraph sync [path]               # Incremental update
codegraph status [path]             # Show statistics (--json available)

# Query
codegraph query <search>            # Search symbols (--kind, --limit, --json)
codegraph explore <query>           # Source + call paths in one shot
codegraph node <symbol|file>        # One symbol's source + callers
codegraph files [path]              # Show file structure (--format, --json)
codegraph callers <symbol>          # Find callers (--json)
codegraph callees <symbol>          # Find callees (--json)
codegraph impact <symbol>           # Blast radius (--json)
codegraph affected [files...]       # Find affected tests

# Agent/MCP integration
codegraph install                   # Wire MCP server into agents
codegraph uninstall                 # Remove agent configs

# Maintenance
codegraph daemon                    # Manage background daemons
codegraph unlock [path]             # Remove stale lock file
codegraph telemetry [action]        # Usage telemetry
codegraph upgrade [version]         # Update CLI (--check to compare versions)
codegraph version                   # Print version

# Meta
codegraph --version                 # Show version (bare semver)
codegraph --help                    # Show help
```

Sources:
- https://colbymchenry.github.io/codegraph/reference/cli/
- `codegraph --help` output (installed v1.3.1)

## CodeGraph-Specific Logic (only these differ from OpenSpec)

| Area | OpenSpec (reference) | CodeGraph (this PR) |
|------|---------------------|---------------------|
| **id** | `openspec` | `codegraph` |
| **kind** | `integrations` | `integrations` |
| **version** | `1.0.0` | `1.4.1` (tracks upstream latest) |
| **Binary name** | `openspec` | `codegraph` |
| **Install method** | `npm` (global package) | `npm` (global package) — also supports curl installer |
| **Install command** | `npm install -g @fission-ai/openspec@latest` | `npm install -g @colbymchenry/codegraph` |
| **Uninstall command** | `npm uninstall -g @fission-ai/openspec` | `npm uninstall -g @colbymchenry/codegraph` |
| **Prerequisites** | Node.js >= 20.19.0 | Node.js (any version) — bundles own runtime |
| **Version regex** | `r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)"` | `r"(\d+\.\d+\.\d+)"` — bare semver, no prefix |
| **Version flag** | `--version` | `--version` |
| **detect() method** | `$PATH` lookup for `openspec` + `--version` | `$PATH` lookup for `codegraph` + `--version` |
| **verify() method** | detect + `openspec --help` smoke test | detect + `codegraph --help` smoke test (no doctor) |
| **Doctor command** | `openspec doctor` (disponible) | ❌ **No doctor CLI** — verify uses `--help` (Context7 pattern) |
| **health() method** | `openspec doctor --json` + exit code hybrid | `codegraph status --json` — always returns exit 0 + valid JSON. JSON used as-is in diagnostics; no project-specific fields evaluated. |
| **Health JSON** | `openspec doctor --json` → `root.healthy` | `codegraph status --json` → `{"version":"...","initialized":...,...}` — JSON returned as diagnostics but only CLI availability is evaluated. No `.codegraph`-specific logic. |
| **Homepage URL** | `https://openspec.dev/` | `https://colbymchenry.github.io/codegraph/` |
| **Docs URL** | `https://openspec.dev/docs/` | `https://colbymchenry.github.io/codegraph/` |
| **Repository URL** | `https://github.com/fission-ai/OpenSpec` | `https://github.com/colbymchenry/codegraph` |
| **Capabilities** | `("sdd", "specs", "changes")` | `("code-intelligence", "knowledge-graph", "mcp")` |
| **Install manager** | `npm` | `npm` |

### Architectural variance: no doctor command + health via `status --json`

CodeGraph does NOT provide a doctor/diagnostic command (same limitation as Context7).

Unlike Context7, CodeGraph offers `codegraph status --json` which **always returns exit 0** and valid JSON, including the `version` field — even when no `.codegraph/` project is initialized. This provides a richer health check than Context7's detect-only approach without introducing project-specific logic.

**Health strategy**:
1. Call `detect()` to confirm the binary exists. If not found → `"down"`.
2. Run `codegraph status --json` and parse the JSON.
3. If exit 0 + valid JSON → `"healthy"`. The full JSON (version, initialized, projectPath, index stats) is returned as `diagnostics`.
4. If the JSON cannot be parsed → fallback to exit code, same hybrid strategy as OpenSpec's `openspec doctor --json`.
5. No project-specific logic: `.codegraph/`, repo state, index health are NOT evaluated. Health evaluates only CLI availability and functioning.
6. Never throw — degrade gracefully on parse errors.

**Verify strategy** (same as Context7 — no doctor):
1. detect() confirms binary + version
2. Run `codegraph --help` as basic responsiveness check
3. Return success if both pass

### Install method (npm only)

CodeGraph is installed via npm, consistent with the Reference Component (OpenSpec):

```
npm install -g @colbymchenry/codegraph
```

The upstream project also offers a standalone install script for environments without Node.js, but the adapter uses npm exclusively — matching the existing component pattern and keeping the prerequisite surface uniform across adapters.

### Uninstall semantics

Like OpenSpec (npm-based), `npm uninstall -g @colbymchenry/codegraph` returns success when the package is not installed. The adapter follows the OpenSpec pattern: return `OperationResult(success=True)` when the tool is already absent.

Note: `codegraph uninstall` also exists but removes MCP agent configs, NOT the CLI binary itself. The adapter targets the binary lifecycle via npm, not the MCP config lifecycle.

### Version output format (bare semver)

Unlike OpenSpec (`openspec 1.6.0`) or Context7 (`ctx7 0.5.4`), CodeGraph's `--version` outputs bare semver (`1.3.1`) with NO prefix. The version regex is correspondingly simpler:

```python
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)", re.MULTILINE)
```

## ADR CliComponent Evaluation Reference

From `openspec/changes/pr7-context7-component/adr-clicomponent-evaluation.md`:

> **Verdict: KEEP CURRENT DESIGN** — shared interface proportion is 31.6% (46 of 145 lines). Well below the 60% threshold that would justify extracting a CliComponent base class.

This PR adds CodeGraph as the fourth adapter. Even with 4 adapters, each follows the same template with only CLI-specific differences — no new abstractions.

## Files (PR8 — Foundation + Core)

Only adapter-specific files. No Core Stack modifications.

### PR8.1 Foundation (scope matches PR6.1, PR7.1)
- CREATE `src/apoch/stack/components/codegraph.py` — CodeGraphComponent with DESCRIPTOR, `_parse_version()`, `__init__(runner)`, and ALL lifecycle methods as `NotImplementedError` stubs (detect, health, install, uninstall, verify, activate, deactivate)
- MODIFY `src/apoch/stack/components/__init__.py` — export CodeGraphComponent + CODEGRAPH_DESCRIPTOR
- MODIFY `pyproject.toml` — entry point for codegraph
- CREATE `tests/stack/components/test_codegraph.py` — foundation tests: descriptor fields, version parser, component instantiation, entry point resolution (NO lifecycle tests)
- CREATE `openspec/changes/pr8-codegraph-component/specs/codegraph-component/spec.md` — spec
- CREATE `openspec/changes/pr8-codegraph-component/design.md` — design
- CREATE `openspec/changes/pr8-codegraph-component/tasks.md` — tasks

### PR8.2 Core Lifecycle (scope matches PR5.3, PR6.2, PR7.2)
- ADD full implementation to lifecycle methods in `codegraph.py`: detect(), health() with `status --json`, install(), uninstall(), verify() with `--help`, activate(), deactivate()
- ADD core lifecycle tests to `test_codegraph.py`
- Full ruff check, pytest suite, entry point validation

## Dependencies
- `apoch.stack` (existing, frozen) — StackComponent ABC, ComponentInfo, StackDescriptor, OperationResult, CommandRunner
- OpenSpec component (reference for structure)
- Context7 component (reference for no-doctor pattern)

## Risks
- **codegraph binary not found** → clear error message, NOT_INSTALLED state
- **Version format bare** → regex handles bare semver correctly; no prefix to strip
- **No doctor command** → verify() uses `--help` (Context7 pattern); health() uses `status --json` which always works
- **npm network/permissions on install** → handled by OperationResult (same pattern as OpenSpec)
- **npm prerequisite** → consistent with OpenSpec/Context7 pattern; official install requires `npm`
- **codegraph CLI vs codegraph MCP server** → the adapter targets the CLI binary lifecycle via npm. `codegraph install`/`codegraph uninstall` manage MCP agent configs, NOT the binary. Binary lifecycle is npm-only.
- **Privacy/telemetry** — `codegraph telemetry` allows changing usage telemetry. Not exposed by the adapter (matches OpenSpec/Context7 pattern — no feature flag management in the adapter).
