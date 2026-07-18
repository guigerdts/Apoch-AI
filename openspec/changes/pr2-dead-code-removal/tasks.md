# Tasks: PR-2 — Dead Code Removal

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1 |
| 400-line budget risk | None |
| Chained PRs recommended | No |
| Delivery strategy | direct |

## Phase 1: Remove Dead Code

### Task 1.1: [x] Remove `isinstance(diag, dict)` check from `_apply_health()`

**Files**: `src/apoch/modules/oracle/engine.py`
**Requirement**: AC-1
**Description**: Remove lines 285–286 of `engine.py` — the `if not isinstance(diag, dict): continue` guard inside `_apply_health()`. This is an impossible condition: every `diag` value comes from Guardian diagnostics which are always `dict[str, Any]`. The `diag.get("diagnostic", str(diag))` call on line 287 already handles non-dict values gracefully, so the guard provides no defense-in-depth value.
**Acceptance**: Single line removal. No behavioral change. Module imports cleanly.

### Task 1.2: [x] Verify existing tests pass

**Files**: `tests/`
**Requirement**: AC-2, AC-3
**Description**: Run `uv run pytest tests/ -x -q --ignore=tests/e2e`. All existing tests MUST pass without modification.
**Acceptance**: Exit code 0.

### Task 1.3: [x] Verify Ruff compliance

**Files**: `src/apoch/modules/oracle/engine.py`
**Requirement**: AC-4
**Description**: Run `uv run ruff check src/apoch/modules/oracle/engine.py` and `uv run ruff format --check src/apoch/modules/oracle/engine.py`. Both MUST pass cleanly.
**Acceptance**: Exit code 0 on both commands.

### Task 1.4: [x] Verify no regressions in observable API behavior

**Files**: `src/apoch/modules/oracle/engine.py`
**Requirement**: AC-5
**Description**: Confirm `RecommendationEngine._apply_health()` still accepts the same `health: dict[str, Any]` parameter and returns the same `Recommendation` type. The method must still degrade confidence for each key in the health dict and annotate evidence. No new dead code introduced.
**Acceptance**: Observable contract identical. Same input → same output.
