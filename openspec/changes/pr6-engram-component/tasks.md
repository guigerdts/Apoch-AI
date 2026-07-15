# Tasks: PR6 — Engram Stack Component

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~450 (+450 / −0) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR per phase |
| Delivery strategy | feature-branch-chain |
| Chain strategy | stacked-to-main |

## Phases

### Phase 1: Foundation — Package + Entry Point (PR6.1)
- [ ] 1.1 Modify `src/apoch/stack/components/__init__.py` — export `EngramComponent` and `ENGRA_DESCRIPTOR`
- [ ] 1.2 Register entry point in `pyproject.toml`: `engram = "apoch.stack.components.engram:EngramComponent"` under `[project.entry-points."apoch.stack.components"]`
- [ ] 1.3 Create `src/apoch/stack/components/engram.py` with:
  - `ENGRA_DESCRIPTOR` constant (id, name, kind, version, install_command per platform, homepage, repository, docs_url, requires=(), capabilities)
  - `_parse_version(stdout) -> str | None` — regex `r"(?:engram\s+)?v?(\d+\.\d+\.\d+)"`
  - `EngramComponent` class with `detect()` stub (raises NotImplementedError — PR6.2 fills it)
  - All other lifecycle stubs (install, verify, health, activate, deactivate, uninstall) raising NotImplementedError
- [ ] 1.4 Verify entry point resolves: `entry_points(group="apoch.stack.components")`

### Phase 2: Core Implementation — EngramComponent (PR6.2)
- [ ] 2.1 Implement `detect()` — `shutil.which("engram")`, `CommandRunner.run(["engram", "version"])`, parse output, return `ComponentInfo`
- [ ] 2.2 Implement `install()` — `platform.system()` dispatch:
  - Darwin: `brew install gentleman-programming/tap/engram`
  - Linux: Homebrew or binary download via curl
  - Windows: `go install github.com/Gentleman-Programming/engram/cmd/engram@latest`
  - Post-install confirm via `self.detect()`
- [ ] 2.3 Implement `verify()` — detect → derive_state → `engram doctor`
- [ ] 2.4 Implement `health()` — detect + `engram doctor` exit code → `{"status": "healthy"|"degraded"|"down"}`
- [ ] 2.5 Implement `activate()` — detect only; `deactivate()` — no-op
- [ ] 2.6 Implement `uninstall()`:
  - If Homebrew path: `brew uninstall engram`
  - If binary path: delete binary + prompt for data dir removal
  - Confirm via `self.detect()`

### Phase 3: Testing (PR6.2)
- [ ] 3.1 Pure-function tests: `test_parse_version_*` (engram prefix, v prefix, bare, nonsense, empty, multiline)
- [ ] 3.2 `detect()` tests (mocked CommandRunner): not installed, success, CLI error
- [ ] 3.3 `install()` tests: brew path, binary path, windows path, each failure mode
- [ ] 3.4 `verify()` tests: not installed, success, doctor fails
- [ ] 3.5 `health()` tests: healthy, degraded, down
- [ ] 3.6 `activate()` / `deactivate()` / `uninstall()` tests

### Phase 4: Final Validation (PR6.2)
- [ ] 4.1 Run `ruff check src/apoch/stack/components/ tests/stack/components/` — zero violations
- [ ] 4.2 Run `pytest tests/stack/ -v` — all pass, no regressions
- [ ] 4.3 Verify entry point resolves: `entry_points(group="apoch.stack.components")`
