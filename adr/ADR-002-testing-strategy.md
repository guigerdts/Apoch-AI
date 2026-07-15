# ADR-002 — Testing Strategy

**Date:** 2026-07-15
**Status:** Proposed
**Context:** Core Stack is frozen, four adapters implemented (OpenSpec, Engram, Context7, CodeGraph), documentation complete. Milestone 3 (Integration & Release) requires a defined testing strategy before any E2E code is written.

---

## 1. Objective

### 1.1 What this ADR guarantees

- Every component lifecycle method is validated at the appropriate level (unit, integration, E2E).
- Test execution is **safe for the developer's machine** — no destructive operations outside CI.
- CI and local environments have clear, non-overlapping responsibilities.
- New adapters follow the same testing pattern without re-debating the strategy.

### 1.2 What is out of scope

- Performance targets (covered by PR13 — Benchmark, non-blocking).
- Specific CI provider configuration (covered by PR11).
- Individual test case design (belongs in each PR's spec).
- Pre-commit hooks or gating (future concern).

---

## 2. Testing Pyramid

```
         ╱╲
        ╱ E2E ╲           ← Real tools, real detect/verify/health/activate/deactivate
       ╱────────╲
      ╱Integration╲        ← MockRunner, no external dependencies
     ╱──────────────╲
    ╱    Unit Tests    ╲   ← Pure logic, no I/O, no subprocess
   ╱────────────────────╲
  ╱     Benchmark        ╲  ← Non-blocking, detect()/verify()/health() only
 ╱────────────────────────╲
```

| Layer | Dependencies | Speed | Blocks merge |
|-------|-------------|-------|-------------|
| Unit | None (pure Python) | < 1ms/test | ✅ Yes |
| Integration | MockRunner | < 10ms/test | ✅ Yes |
| E2E | Real CLI tools installed | < 1s/test | ✅ Yes |
| Benchmark | Real CLI tools installed | varies | ❌ No (informational) |

---

## 3. Classification — pytest markers

| Marker | Scope | Requirement |
|--------|-------|-------------|
| `unit` | Pure logic, no I/O, no subprocess | Never depends on external software |
| `integration` | Uses `MockRunner` to simulate CLI | No real external dependencies |
| `e2e` | Real CLI tools installed on the system | Requires specific tool in PATH |
| `benchmark` | Performance measurement of detect/verify/health | Requires real tools, runs on demand |
| `slow` | Any test that takes > 1s to execute | Informational, not a blocker |

Tests without a marker default to `unit` behaviour wherever possible.

---

## 4. Rules

### 4.1 Unit tests

- Zero external dependencies — no subprocess, no filesystem, no network.
- Test pure logic: version parsing, state derivation, descriptor validation, error formatting.
- Must not import or instantiate `StackComponent` subclasses that trigger CLI discovery.

### 4.2 Integration tests

- Use `MockRunner` (provided by `tests/stack/_testing.py`) to simulate CLI output and exit codes.
- Cover every lifecycle method at least once: detect, install, uninstall, verify, activate, deactivate, health.
- Test state transition paths under the full `derive_state()` matrix.
- Test error paths: disk full, permission denied, timeout, corrupted output, missing binary.

### 4.3 E2E tests

- Run against **real CLI tools** installed on the system.
- Cover: `detect()`, `verify()`, `health()`, `activate()`, `deactivate()`.
- **`install()` and `uninstall()` MUST NEVER run on a developer's machine** — they are only executed in ephemeral CI runners.
- A test MUST detect whether the required tool is available (`shutil.which`) and skip gracefully with `pytest.skip(reason="tool not found")` — never fail due to missing tooling.
- E2E tests that require a tool not present on the current system are **skipped, not failed**.

### 4.4 Benchmark tests

- Non-blocking — never gate a merge.
- Scope: `detect()`, `verify()`, `health()` per adapter.
- Run manually or on demand in CI — not part of the default `pytest` suite.
- Results are informational: track regressions, no pass/fail threshold.

### 4.5 Destructive operations policy

- `install()` and `uninstall()` are **destructive operations**.
- They MUST NEVER execute in any test that runs on a developer's machine.
- In CI, they MUST run only in **ephemeral runners** where no real tools need preserving.
- Detection: a test can verify `os.environ.get("CI")` is truthy and/or the marker requires explicit `--run-destructive` flag overrides.

---

## 5. Supported environments

| Environment | Unit | Integration | E2E | Benchmark | Destructive (install/uninstall) |
|-------------|------|-------------|-----|-----------|----------------------------------|
| Linux (ubuntu-latest) | ✅ | ✅ | ✅ (all 4 tools) | ✅ | ✅ |
| macOS (macos-latest) | ✅ | ✅ | ✅ (all 4 tools) | ✅ | ✅ |
| Windows (windows-latest, native) | ✅ | ✅ | ✅ (best effort) | ✅ | ✅ |
| Developer machine (Linux/macOS) | ✅ | ✅ | ✅ (skip missing tools) | Manual | ❌ Never |
| Termux (Android) | ✅ | ✅ | ⚠️ Best effort | Manual | ❌ Never |

---

## 6. Success criteria per adapter

Every adapter must validate the following methods with real tools in E2E:

| Method | Must pass E2E |
|--------|---------------|
| `detect()` | ✅ Returns `ComponentInfo` with correct version and executable path |
| `verify()` | ✅ Returns `OperationResult(success=True)` |
| `health()` | ✅ Returns `{"status": "healthy"}` (or `"degraded"` if acceptable) |
| `activate()` | ✅ Returns `OperationResult(success=True)` |
| `deactivate()` | ✅ Returns `OperationResult(success=True)` |
| `install()` | ✅ Only in CI ephemeral environments |
| `uninstall()` | ✅ Only in CI ephemeral environments |

---

## 7. Relationship with PR10–PR14

```
ADR-002 ──────────────────▶ PR10.1 ──▶ PR10.2 ──▶ PR11 ──▶ PR12 ──▶ PR13 ──▶ PR14
(policy contract)       (infra only)  (real tools)  (matrix)  (cov)  (bench)  (release)
```

| PR | Depends on | Delivers |
|----|-----------|----------|
| **ADR-002** | — | Testing strategy contract |
| **PR10.1** | ADR-002 approved | `tests/e2e/` structure, fixtures, helpers, env detection, `@pytest.mark.e2e`, pytest config — no real tools yet |
| **PR10.2** | PR10.1 | Real tool validation for all 4 adapters |
| **PR11** | PR10.2 | CI/CD matrix (Linux, macOS, Windows native) |
| **PR12** | PR11 | Coverage config, XML report, badge |
| **PR13** | PR12 | Benchmark for detect/verify/health |
| **PR14** | PR13 | CHANGELOG, tag v1.0.0, GitHub Release, PyPI |

---

## 8. Explicit decisions

| Decision | Rationale |
|----------|-----------|
| **No Docker** | Docker adds complexity, masks platform-specific issues, and requires daemon setup. The E2E CI matrix runs on native OS runners. |
| **No mocks in E2E** | E2E tests exist precisely to validate real tool behaviour. Mocked E2E is integration testing under a different name. |
| **CI is the only environment for destructive tests** | Developers must never risk losing installed tools. Ephemeral runners are the only safe environment for install/uninstall validation. |
| **Benchmarks are informational, not blocking** | Performance is tracked for regression awareness, not gating. False positives from benchmark noise would block unrelated changes. |
| **Coverage threshold: ≥80% overall, ≥90% for `stack/`** | The `stack/` package is the frozen Core — highest stability requirement. Overall 80% allows some modules to trail without blocking v1.0.0. |
| **`@pytest.mark.e2e` tests skip instead of fail when tools are missing** | A developer without `openspec` installed should see "4 skipped", not "4 failed". Missing tooling is an environment choice, not a regression. |

---

## 9. ADR Metadata

- **Approved by**: (pending — to be approved before any E2E implementation)
- **Triggered by**: Milestone 3 planning — need for explicit testing strategy before PR10
- **Evidence**: Four real adapter implementations, Core Stack frozen, documentation complete
- **Next review**: When a fifth adapter is added, or if CI matrix reveals environment gaps
