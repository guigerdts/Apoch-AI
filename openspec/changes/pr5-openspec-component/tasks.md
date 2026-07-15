# Tasks: PR5 — OpenSpec Stack Component

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~440 (+440 / −0) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | size-exception |

## Phases

### Phase 1: Foundation — Package + Entry Point (PR5.1 ✅)
- [x] 1.1 Create `src/apoch/stack/components/__init__.py`
- [x] 1.2 Register entry point in `pyproject.toml`

### Phase 2: Core Implementation — OpenSpecComponent (PR5.2)
- [x] 2.1 Create `src/apoch/stack/components/openspec.py` with DESCRIPTOR
- [x] 2.2 Implement `_parse_version(stdout) -> str | None`
- [x] 2.3 Implement `_parse_node_version(stdout)` and `detect()`
- [x] 2.4 Implement `install()`
- [x] 2.5 Implement `verify()`, `health()`, `activate()`, `deactivate()`
- [x] 2.6 Implement `uninstall()`

### Phase 3: CLI Enrichment (PR5.2)
- [x] 3.1 Enrich `apoch stack status` — show homepage, repository, docs_url, install_command

### Phase 4: Testing (PR5.2)
- [x] 4.1 Pure-function tests: `test_parse_version_*`
- [x] 4.2 `detect()` tests (mocked CommandRunner)
- [x] 4.3 `install()` tests
- [x] 4.4 `verify()` tests
- [x] 4.5 `health()` tests
- [x] 4.6 `activate()` / `deactivate()` / `uninstall()` tests

### Phase 5: Final Validation (PR5.2)
- [x] 5.1 Run `ruff check` — zero violations
- [x] 5.2 Run `pytest tests/stack/ -v` — all pass
- [x] 5.3 Verify entry point resolves via `entry_points()`
