# PR7 — Context7 Stack Component Proposal

## Intent
Integrate Context7 as the third `apoch stack` component. Apoch does NOT implement Context7 — it acts as an adapter to the official project via its public CLI.

Context7 is a documentation intelligence tool for AI coding agents: an npm CLI package that resolves library IDs and fetches up-to-date, version-specific documentation from a curated index.

**Reference Component**: OpenSpec (PR5). Context7 follows the exact same structure, lifecycle, and patterns, changing only the adapter-specific logic.

## Core Stack Philosophy (MANDATORY — ALL components)
Apoch does NOT implement any component. It only acts as an adapter to each official project using its public interface. All project-specific information (install command, URLs, version detection, prerequisites) must come from the official project — never hardcoded from assumptions.

## Governance Compliance

| Rule | Status |
|------|--------|
| 1. Core Stack frozen | ✅ No modifications to StackComponent, StackDescriptor, ComponentInfo, ComponentStatus, StackManager, StackState, derive_state(), or CLI |
| 2. CliComponent deferred | ✅ Only 2 adapters exist (OpenSpec + Engram). Not evaluating abstraction yet. After PR7, with 3 real adapters, evaluation begins. |
| 3. PRs bounded | ✅ Target ≤1200 lines per PR. Forecast: Foundation (~250) + Core (~550) = ~800 total. OK for force-chained. |
| 4. Public interfaces only | ✅ ctx7 public CLI only. No internal files, undocumented endpoints, or unreleased commands. |
| 5. Reference Component Rule | ✅ OpenSpec is the reference. Any structural difference must be justified by a documented Context7 limitation. |

## Context7 Public Interface (verified against official docs)

Source: https://github.com/upstash/context7 (ctx7 CLI v0.5.4 — Jul 6, 2026)
License: MIT
Docs: https://context7.com/docs
CLI docs: https://context7.com/docs/clients/cli
npm: https://www.npmjs.com/package/ctx7

| Interface | Details | Source |
|-----------|---------|--------|
| **Homepage** | `https://context7.com` | README |
| **Repository** | `https://github.com/upstash/context7` | npm registry |
| **Docs** | `https://context7.com/docs` | Official site |
| **CLI binary** | `ctx7 <command>` — npm package (Node.js 18+) | CLI docs |
| **npm package** | `ctx7` (latest: 0.5.4) | npm registry |
| **Version** | `ctx7 --version` → semver (e.g., `0.5.4`) | CLI docs + npm registry |
| **Install** | `npm install -g ctx7` | CLI docs |
| **Uninstall** | `npm uninstall -g ctx7` | CLI docs |
| **Doctor/Health CLI** | ❌ **NO EXISTE** — confirmed from full command reference, changelog, --help, and source. Context7 has an API health endpoint (`/api/health`) for enterprise Docker deployments, NOT for the CLI. | CLI docs + changelog + source |
| **Verification substitute** | `ctx7 --help` — returns exit 0 when binary responds | Confirmed from --help flag docs |
| **Output JSON** | `--json` flag on `ctx7 docs <libraryId> <query>` (NOT on health/version) | CLI source (commands/docs.ts) |
| **Requirements** | Node.js 18+ (npm global install) | CLI docs |

### Available CLI commands (verified)

```bash
# Documentation
ctx7 library <name> <query>           # Resolve library ID
ctx7 docs <libraryId> <query>         # Fetch docs (--json available)

# Skills
ctx7 skills install /owner/repo       # Install from repo
ctx7 skills search <keywords>         # Search registry
ctx7 skills suggest                   # Auto-suggest by project deps
ctx7 skills list                      # List installed skills
ctx7 skills remove <name>             # Uninstall skill
ctx7 skills generate                  # Generate skill with AI (requires login)

# Setup
ctx7 setup                            # Configure Context7 MCP (interactive)
ctx7 login                            # Log in (higher rate limits)
ctx7 whoami                           # Check login status

# Meta
ctx7 --version                        # Show version
ctx7 --help                           # Show help
```

Source: https://github.com/upstash/context7/blob/master/skills/context7-cli/SKILL.md

## Context7-Specific Logic (only these differ from OpenSpec)

| Area | OpenSpec (reference) | Context7 (this PR) |
|------|---------------------|---------------------|
| **id** | `openspec` | `context7` |
| **kind** | `integrations` | `integrations` |
| **version** | `1.0.0` | `0.5.4` (tracks upstream latest) |
| **Binary name** | `openspec` | `ctx7` |
| **Install method** | `npm` (global package) | `npm` (global package) |
| **Install command** | `npm install -g @fission-ai/openspec@latest` | `npm install -g ctx7` |
| **Uninstall command** | `npm uninstall -g @fission-ai/openspec` | `npm uninstall -g ctx7` |
| **Prerequisites** | Node.js >= 20.19.0 | Node.js >= 18.0.0 |
| **Version parser regex** | `r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)"` | `r"(?:ctx7\s+)?v?(\d+\.\d+\.\d+)"` |
| **Version flag** | `--version` | `--version` |
| **detect() method** | `$PATH` lookup for `openspec` + `--version` | `$PATH` lookup for `ctx7` + `--version` |
| **verify() method** | detect + `openspec --help` smoke test | detect + `ctx7 --help` smoke test |
| **Doctor command** | `openspec doctor` (disponible) | ❌ **No doctor CLI** — verify uses `--help` as responsiveness check |
| **health() method** | `openspec doctor --json` + exit code hybrid | Binary + version check only (no doctor available) |
| **Health JSON** | `openspec doctor --json` → `root.healthy` | N/A — no structured health output |
| **Homepage URL** | `https://openspec.dev/` | `https://context7.com` |
| **Docs URL** | `https://openspec.dev/docs/` | `https://context7.com/docs` |
| **Capabilities** | `("specs", "design", "tasks", "changes")` | `("docs", "skills", "mcp")` |

### Architectural variance: no doctor command

This is the first adapter where the upstream project does NOT provide a doctor/diagnostic CLI command. The impact:

- **verify()**: After detect() confirms the binary exists and version parses, the method runs `ctx7 --help` as a basic responsiveness check. This is functionally equivalent to OpenSpec's `--help` check but CANNOT include a deeper diagnostic step.
- **health()**: Returns `{"status": "healthy", ...}` when binary + version are confirmed, without the deeper diagnostic that OpenSpec/Engram provide. This is a conscious architectural limitation of the upstream CLI — Context7's health endpoint only exists for enterprise Docker deployments, not for the CLI tool.

### Uninstall semantics
Like OpenSpec (npm-based), `npm uninstall -g ctx7` returns success when the package is not installed. The adapter will follow the OpenSpec pattern: return `OperationResult(success=True)` when the tool is already absent, since no action is needed. This differs from Engram's `success=False` for the same case (brew semantics).

## Files (PR7 — Foundation + Core)

Only adapter-specific files. No Core Stack modifications.

### PR7.1 Foundation
- CREATE `src/apoch/stack/components/context7.py` — Context7Component (adapter: DESCRIPTOR, parser, detect())
- MODIFY `src/apoch/stack/components/__init__.py` — export Context7Component + DESCRIPTOR
- MODIFY `pyproject.toml` — entry point for context7
- CREATE `tests/stack/components/test_context7.py` — foundation tests (detect, parser, descriptor)
- CREATE `openspec/changes/pr7-context7-component/specs/context7-component.md` — spec
- CREATE `openspec/changes/pr7-context7-component/design.md` — design
- CREATE `openspec/changes/pr7-context7-component/tasks.md` — tasks

### PR7.2 Core
- ADD lifecycle methods to `context7.py`: install(), uninstall(), verify(), activate(), deactivate(), health()
- ADD core tests to `test_context7.py`: lifecycle tests

## Dependencies
- `apoch.stack` (existing, frozen) — StackComponent ABC, ComponentInfo, StackDescriptor, OperationResult, CommandRunner
- OpenSpec component (reference for structure)

## Risks
- **ctx7 binary not found** → clear error message, NOT_INSTALLED state
- **Version format changes** → robust regex parser with logging, never crashes
- **No doctor command** → verify() and health() are shallower than OpenSpec/Engram. Documented as architectural limitation of the upstream CLI. health() returns "healthy" based on binary detection only.
- **npm network/permissions on install** → handled by OperationResult (same pattern as OpenSpec)
- **Node.js 18+ requirement** → documented in `requires` field; not enforced by the adapter (same as OpenSpec)
- **ctx7 vs context7 binary confusion** → confirmed: binary is `ctx7`, the npm package is `ctx7`. The older `context7` package (binary `c7`, v1.0.3) is a different project; the adapter targets `ctx7`.
