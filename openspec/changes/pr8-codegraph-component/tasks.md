# Tasks: PR8 — CodeGraph Stack Component

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~620 total (PR8.1 ~180, PR8.2 ~440) |
| 400-line budget risk | Low (PR8.1) / Medium (PR8.2) |
| Chained PRs recommended | Yes |
| Suggested split | PR8.1 Foundation → PR8.2 Core Lifecycle |
| Delivery strategy | force-chained |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: DESCRIPTOR, parser, `__init__`, stubs, exports, entry point | PR 8.1 | `uv run pytest tests/stack/components/test_codegraph.py -x -k "TestDescriptor or TestParseVersion or TestComponent or TestEntryPoint"` | `uv run python -c "from apoch.stack.components.codegraph import CodeGraphComponent, CODEGRAPH_DESCRIPTOR; print('OK')"` | revert codegraph.py + __init__.py + pyproject.toml + foundation test sections |
| 2 | Core Lifecycle: detect, health, install, uninstall, verify, activate, deactivate | PR 8.2 | `uv run pytest tests/stack/components/test_codegraph.py -x` | `uv run python -c "from apoch.stack.components.codegraph import CodeGraphComponent; c = CodeGraphComponent(); print('OK')"` | revert lifecycle implementations + core test sections |

## Phase 1: Foundation — PR8.1

- [x] 1.1 Create `src/apoch/stack/components/codegraph.py` — CODEGRAPH_DESCRIPTOR (id=codegraph, capabilities=("code-intelligence", "knowledge-graph", "mcp"), requires=("node",), install_command="npm install -g @colbymchenry/codegraph")
- [x] 1.2 Add `_parse_version()` — bare semver regex `r"(\d+\.\d+\.\d+)"`, returns `str | None`
- [x] 1.3 Add `CodeGraphComponent` class with `__init__(runner=None)` and `descriptor` property
- [x] 1.4 Add ALL lifecycle methods as `NotImplementedError` stubs: detect(), health(), install(), uninstall(), verify(), activate(), deactivate()
- [x] 1.5 Edit `src/apoch/stack/components/__init__.py` — add `CODEGRAPH_DESCRIPTOR` + `CodeGraphComponent` exports
- [x] 1.6 Edit `pyproject.toml` — add codegraph entry point to `apoch.stack.components` group
- [x] 1.7 Create `tests/stack/components/test_codegraph.py` — foundation: descriptor fields, version parser (bare semver, edge cases), component constructor/descriptor, entry point resolution, stub raises NotImplementedError

## Phase 2: Core Lifecycle — PR8.2

- [x] 2.1 Implement `detect()` — shutil.which("codegraph") + --version + `_parse_version()`
- [x] 2.2 Implement `health()` — `codegraph status --json` with JSON parse + exit-code fallback
- [x] 2.3 Implement `install()` — `npm install -g @colbymchenry/codegraph` + detect() confirmation
- [x] 2.4 Implement `uninstall()` — `npm uninstall -g @colbymchenry/codegraph` + absent-noop
- [x] 2.5 Implement `verify()` — detect() + `codegraph --help` smoke test (Context7 no-doctor pattern)
- [x] 2.6 Implement `activate()` / `deactivate()` — binary-check + no-op
- [x] 2.7 Add core lifecycle tests — detect (installed/missing/version-fails), health (down/healthy-via-JSON/JSON-unparseable-fallback), install (success/fail/not-found-after), uninstall (success/fail/not-installed), verify (success/fail-not-installed/help-fails), activate (installed/not), deactivate (always-succeeds)

## Phase 3: Verification

- [ ] 3.1 Run full test suite — `uv run pytest tests/stack/components/test_codegraph.py -v`
- [ ] 3.2 Verify entry point — `uv run python -c "from importlib.metadata import entry_points; eps = entry_points(group='apoch.stack.components'); assert any(ep.name=='codegraph' for ep in eps)"`
- [ ] 3.3 Confirm Core Stack not modified — `ruff check src/apoch/stack/component.py src/apoch/stack/descriptor.py src/apoch/stack/manager.py src/apoch/stack/state.py`
