# Design: PR5 — OpenSpec Stack Component

## Technical Approach

Implement `OpenSpecComponent` as the first real `apoch.stack` component — an adapter to the official OpenSpec project via its public CLI. Follows the three-layer pipeline: **StackDescriptor** (declarative) → **ComponentInfo** (factual, from `detect()`) → **StackState** (derived via `derive_state()`). Zero changes to `StackManager` — it orchestrates via the `StackComponent` ABC.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI version regex | Single regex `r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)"` | Covers current + future formats without branching |
| Dependency injection | Constructor injection: `runner`, `clock` optional | Matches existing component pattern, fully testable |
| Node.js prerequisite | Hard block | OpenSpec requires Node.js; partial install wastes time |
| Activate/deactivate | `activate()` verifies detect; `deactivate()` no-op | OpenSpec is a global CLI — no session state |
| File location | `src/apoch/stack/components/openspec.py` | Single responsibility; `components/` package ready for siblings |

## Data Flow

```
StackManager.verify("openspec")
    │
    ├──→ OpenSpecComponent.detect()
    │       ├── shutil.which("openspec") → None → ComponentInfo(installed=False)
    │       └── which OK → CommandRunner.run(["openspec", "--version"])
    │               └── stdout → _parse_version() → ComponentInfo(installed=True, version="1.6.0")
    │
    ├──→ derive_state(descriptor, info)
    │       ├── NOT_INSTALLED → early return (failure)
    │       ├── OUTDATED/UNSUPPORTED → diagnostic failure
    │       └── INSTALLED → continue
    │
    └──→ OpenSpecComponent.verify()
            └── CommandRunner.run(["openspec", "--help"])
                    ├── returncode 0 → OperationResult(success=True)
                    └── non-zero   → OperationResult(success=False)
```

## Key Method Contracts

**`detect()`**: Pure factual observation. Never infers state. On version parse failure: logs warning, returns `version=None`.

**`install()`**: Prerequisite-first. Checks `node --version` before running npm. Returns `OperationResult(success=False)` with descriptive message if Node.js is missing or too old.

**`verify()`**: Three-phase: detect → derive_state → integrity. Re-runs detect() for freshness. Integrity check via `openspec --help`.

**`health()`**: Beyond verify — runs `openspec --help` and checks output. Returns `{"status": "down"|"degraded"|"healthy"}`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/stack/components/openspec.py` | Create | OpenSpecComponent — all 7 lifecycle methods |
| `src/apoch/stack/components/__init__.py` | Create | Package init, exports |
| `pyproject.toml` | Modify | Add entry point |
| `tests/stack/components/test_openspec.py` | Create | 30+ tests covering all lifecycle methods |
| `src/apoch/cli/stack.py` | Modify | CLI enrichment — enhanced stack status |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_parse_version()` — formats, garbage, empty, multiline | Parametrized pure function tests |
| Unit | `detect()` — not found, valid version, CLI error | Mock `shutil.which` + MockRunner |
| Unit | `install()` — node ok, node missing, node too old, npm fails | MockRunner for both node and npm |
| Unit | `verify()` — installed + passes, installed + fails, not installed | MockRunner |
| Unit | `health()` — healthy, degraded, down | MockRunner + fixture output |
| Unit | `activate()` / `deactivate()` / `uninstall()` | MockRunner |
| Integration | Entry-point resolution via registry.discover() | Real import |
