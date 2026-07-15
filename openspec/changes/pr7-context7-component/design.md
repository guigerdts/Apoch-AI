# Design: PR7 — Context7 Stack Component

## Technical Approach

Implement `Context7Component` as the third `apoch.stack` component — an adapter to the official Context7 project via its public CLI (`ctx7`). Follows the three-layer pipeline: **StackDescriptor** (declarative) → **ComponentInfo** (factual, from `detect()`) → **StackState** (derived via `derive_state()`). Zero changes to Core Stack — identical architectural pattern to OpenSpec (Reference Component).

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI binary name | `ctx7` | Binary name is `ctx7`, NOT `context7` or `c7`. Verified from official docs and npm registry (`bin: ctx7`). |
| CLI version regex | Single regex `r"(?:ctx7\s+)?v?(\d+\.\d+\.\d+)"` | Covers current (`0.5.4`), with-prefix, and with-`v` formats without branching |
| Dependency injection | Constructor injection: `runner` optional | Matches existing component pattern, fully testable |
| Prerequisites | `requires=("node>=18",)` | Node.js 18+ required per official docs (same npm pattern as OpenSpec) |
| Install method | Single: `npm install -g ctx7` | Context7 has a single universal install command (unlike Engram's platform dispatch) |
| Uninstall | `npm uninstall -g ctx7` | Returns success when already absent (npm semantics, same as OpenSpec) |
| Activate/deactivate | `activate()` verifies detect; `deactivate()` no-op | CLI binary — no session state |
| **No doctor command** | verify uses `ctx7 --help`; health uses binary+version only | Context7 CLI has NO `doctor` or health command — verified from official docs, --help, command reference, changelog, and source. This is a documented architectural limitation of the upstream CLI. |
| File location | `src/apoch/stack/components/context7.py` | Single responsibility; follows OpenSpec/Engram pattern exactly |

## Data Flow

```
StackManager.verify("context7")
    │
    ├──→ Context7Component.detect()
    │       ├── shutil.which("ctx7") → None → ComponentInfo(installed=False)
    │       └── which OK → CommandRunner.run(["ctx7", "--version"])
    │               └── stdout → _parse_version() → ComponentInfo(installed=True, version="0.5.4")
    │
    ├──→ derive_state(descriptor, info)
    │       ├── NOT_INSTALLED → early return (failure)
    │       ├── OUTDATED/UNSUPPORTED → diagnostic failure
    │       └── INSTALLED → continue
    │
    └──→ Context7Component.verify()
            └── CommandRunner.run(["ctx7", "--help"])
                    ├── returncode 0 → OperationResult(success=True)
                    └── non-zero   → OperationResult(success=False)
```

```
Context7Component.install()
    │
    ├── CommandRunner.run(["npm", "install", "-g", "ctx7"])
    │       ├── success → self.detect() → OperationResult(success=True)
    │       └── failure → OperationResult(success=False, message=...)
    │
    └── return OperationResult
```

```
Context7Component.health()
    │
    ├── self.detect()
    │       ├── not installed → {"status": "down", "component": "context7"}
    │       ├── installed + version → {"status": "healthy"}
    │       └── installed + no version → {"status": "degraded", "diagnostics": {...}}
    │
    └── return dict
```

**Note on shallower health check**: Unlike OpenSpec (`openspec doctor --json`) and Engram (`engram doctor`), Context7 has no equivalent diagnostic command. The health check returns "healthy" based solely on binary existence + version parseability. This is correct behavior for this adapter — the upstream CLI does not expose deeper diagnostics.

## Key Method Contracts

**`detect()`**: Pure factual observation. Never infers state. On version parse failure: logs warning, returns `version=None`. Identical to OpenSpec/Engram.

**`install()`**: Single universal command — `npm install -g ctx7`. No platform dispatch (unlike Engram). Returns success when npm finishes. Post-install confirm via `self.detect()`.

**`verify()`**: Two-phase: detect → derive_state → functional check. Functional check uses `ctx7 --help` as a responsiveness test (no doctor command available).

**`health()`**: Returns `{"status": "down"|"degraded"|"healthy"}`. "healthy" = binary exists + version parseable. "degraded" = binary exists but version unparseable. "down" = not installed.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/stack/components/context7.py` | Create | Context7Component — all 7 lifecycle methods |
| `src/apoch/stack/components/__init__.py` | Modify | Export Context7Component + DESCRIPTOR |
| `pyproject.toml` | Modify | Add entry point |
| `tests/stack/components/test_context7.py` | Create | Tests covering all lifecycle methods |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_parse_version()` — formats, garbage, empty, multiline | Parametrized pure function tests |
| Unit | `detect()` — not found, valid version, CLI error | Mock `shutil.which` + MockRunner |
| Unit | `install()` — npm install success, failure | MockRunner |
| Unit | `verify()` — installed + help passes, installed + help fails, not installed | MockRunner |
| Unit | `health()` — healthy, degraded (version unparseable), down | MockRunner + fixture output |
| Unit | `activate()` / `deactivate()` / `uninstall()` — npm uninstall (success, failure, not installed) | MockRunner |
| Integration | Entry-point resolution via registry.discover() | Real import |

## Commit Strategy (force-chained)

**PR7.1 Foundation**: DESCRIPTOR, parser, detect(), entry point, foundation tests
**PR7.2 Core**: install(), uninstall(), verify(), activate(), deactivate(), health(), core tests
