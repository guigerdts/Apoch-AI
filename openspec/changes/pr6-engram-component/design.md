# Design: PR6 — Engram Stack Component

## Technical Approach

Implement `EngramComponent` as the second `apoch.stack` component — an adapter to the official Engram project via its public CLI. Follows the three-layer pipeline: **StackDescriptor** (declarative) → **ComponentInfo** (factual, from `detect()`) → **StackState** (derived via `derive_state()`). Zero changes to Core Stack — identical architectural pattern to OpenSpec.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CLI version regex | Single regex `r"(?:engram\s+)?v?(\d+\.\d+\.\d+)"` | Covers current + future formats without branching |
| Dependency injection | Constructor injection: `runner` optional | Matches existing component pattern, fully testable |
| No prerequisites | Empty requires tuple | Engram is a static Go binary — zero runtime dependencies |
| Platform-selected install | `platform.system()` dispatch | Engram has no single universal install command; each platform has a documented method |
| Activate/deactivate | `activate()` verifies detect; `deactivate()` no-op | Engram is a CLI binary — no session state |
| Health check | `engram doctor` — official diagnostic command | Purpose-built read-only health verification |
| File location | `src/apoch/stack/components/engram.py` | Single responsibility; follows OpenSpec pattern exactly |

## Data Flow

```
StackManager.verify("engram")
    │
    ├──→ EngramComponent.detect()
    │       ├── shutil.which("engram") → None → ComponentInfo(installed=False)
    │       └── which OK → CommandRunner.run(["engram", "version"])
    │               └── stdout → _parse_version() → ComponentInfo(installed=True, version="1.19.0")
    │
    ├──→ derive_state(descriptor, info)
    │       ├── NOT_INSTALLED → early return (failure)
    │       ├── OUTDATED/UNSUPPORTED → diagnostic failure
    │       └── INSTALLED → continue
    │
    └──→ EngramComponent.verify()
            └── CommandRunner.run(["engram", "doctor"])
                    ├── returncode 0 → OperationResult(success=True)
                    └── non-zero   → OperationResult(success=False)
```

```
EngramComponent.install()
    │
    ├── platform.system() dispatch:
    │   ├── Darwin  → "brew install gentleman-programming/tap/engram"
    │   ├── Linux   → "curl ... | tar -xz" or Homebrew
    │   └── Windows → "go install github.com/Gentleman-Programming/engram/cmd/engram@latest"
    │
    ├── CommandRunner.run(install_cmd)
    │       ├── success → self.detect() → OperationResult(success=True)
    │       └── failure → OperationResult(success=False, message=...)
    │
    └── return OperationResult
```

## Key Method Contracts

**`detect()`**: Pure factual observation. Never infers state. On version parse failure: logs warning, returns `version=None`. Identical to OpenSpec.

**`install()`**: Platform-aware. Dispatches to the appropriate install command for the detected OS. No prerequisite checks (static Go binary). Post-install confirm via `self.detect()`.

**`verify()`**: Three-phase: detect → derive_state → integrity. Re-runs detect() for freshness. Integrity check via `engram doctor`.

**`health()`**: Beyond verify — runs `engram doctor` and checks exit code. Returns `{"status": "down"|"degraded"|"healthy"}`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/stack/components/engram.py` | Create | EngramComponent — all 7 lifecycle methods |
| `src/apoch/stack/components/__init__.py` | Modify | Export EngramComponent + DESCRIPTOR |
| `pyproject.toml` | Modify | Add entry point |
| `tests/stack/components/test_engram.py` | Create | Tests covering all lifecycle methods |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_parse_version()` — formats, garbage, empty, multiline | Parametrized pure function tests |
| Unit | `detect()` — not found, valid version, CLI error | Mock `shutil.which` + MockRunner |
| Unit | `install()` — brew path, binary path, windows path, each fails | MockRunner + monkeypatch platform |
| Unit | `verify()` — installed + passes, installed + fails, not installed | MockRunner |
| Unit | `health()` — healthy, degraded, down | MockRunner + fixture output |
| Unit | `activate()` / `deactivate()` / `uninstall()` | MockRunner |
| Integration | Entry-point resolution via registry.discover() | Real import |
