# Tasks: PR7 — Context7 Stack Component

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~450 (+450 / −0) |
| 1200-line budget risk | Low |
| Chained PRs recommended | Yes (force-chained: PR7.1 → PR7.2) |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

## Phases

### PR7.1: Foundation — Package + Entry Point
- [x] 1.1 Modify `src/apoch/stack/components/__init__.py` — export `Context7Component` and `CONTEXT7_DESCRIPTOR`
- [x] 1.2 Register entry point in `pyproject.toml`: `context7 = "apoch.stack.components.context7:Context7Component"` under `[project.entry-points."apoch.stack.components"]`
- [x] 1.3 Create `src/apoch/stack/components/context7.py` with:
  - `CONTEXT7_DESCRIPTOR` constant (id="context7", name="Context7", kind="integrations", version="0.5.4", install_command="npm install -g ctx7", install_manager="npm", homepage, repository, docs_url, requires=("node>=18",), capabilities=("docs", "skills", "mcp"))
  - `_parse_version(stdout) -> str | None` — regex `r"(?:ctx7\s+)?v?(\d+\.\d+\.\d+)"`
  - `Context7Component` class with `detect()` fully implemented
  - All other lifecycle stubs (install, verify, health, activate, deactivate, uninstall) raising NotImplementedError
- [x] 1.4 Verify entry point resolves: `entry_points(group="apoch.stack.components")`

### PR7.2: Core Implementation — Lifecycle + Tests
- [x] 2.1 Implement `detect()` — `shutil.which("ctx7")`, `CommandRunner.run(["ctx7", "--version"])`, parse output, return `ComponentInfo`
- [x] 2.2 Implement `install()` — `CommandRunner.run(["npm", "install", "-g", "ctx7"])`, post-install confirm via `self.detect()`
- [x] 2.3 Implement `verify()` — detect → derive_state → `ctx7 --help` (no doctor command available)
- [x] 2.4 Implement `health()` — detect only: binary found + version parseable → "healthy"; version unparseable → "degraded"; not found → "down"
- [x] 2.5 Implement `activate()` — detect only; `deactivate()` — no-op
- [x] 2.6 Implement `uninstall()` — `CommandRunner.run(["npm", "uninstall", "-g", "ctx7"])`, return success when already absent (npm semantics), confirm via `self.detect()`
- [x] 2.7 Pure-function tests: `test_parse_version_*` (ctx7 prefix, v prefix, bare, nonsense, empty, multiline)
- [x] 2.8 `detect()` tests (mocked CommandRunner): not installed, success, CLI error
- [x] 2.9 `install()` tests: npm install success, failure
- [x] 2.10 `verify()` tests: not installed, help succeeds, help fails
- [x] 2.11 `health()` tests: healthy, degraded (version unparseable), down
- [x] 2.12 `activate()` / `deactivate()` / `uninstall()` tests (including npm uninstall of already-absent package)

### Final Validation
- [x] 3.1 Run `ruff check src/apoch/stack/components/ tests/stack/components/` — zero violations
- [x] 3.2 Run `pytest tests/stack/ -v` — all pass, no regressions
- [ ] 3.3 Structural comparison with OpenSpec — document differences in archive-report

## Notes
- Context7 CLI has NO `doctor` command — verify() uses `--help`, health() uses detect() only
- npm uninstall returns success when package is absent — follow OpenSpec pattern (success=True), NOT Engram pattern (success=False)
- Single install command — no platform dispatch needed (unlike Engram)
