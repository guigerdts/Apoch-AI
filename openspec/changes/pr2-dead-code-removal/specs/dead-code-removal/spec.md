# PR-2: Dead Code Removal — Specification

## Objective

Eliminar código muerto en `_apply_health()` de `oracle/engine.py`.

## Scope

**Included:**

1. Remove the dead `isinstance(diag, dict)` check from `_apply_health()` in `src/apoch/modules/oracle/engine.py` (line 285–286)
2. Update any affected tests if they specifically test this dead code path
3. Verify that the observable API behavior does not change

**Excluded:**

- Refactors
- Architecture improvements
- Optimizations
- Naming changes
- Style changes
- Any "ya que estamos" cleanup
- Any other dead code not confirmed by the audit

**Dead code criteria:** Every removed line MUST be:
- Unreachable, OR
- An impossible condition (isinstance that can never be False), OR
- Covered by tests proving it never executes, OR
- Replaced by another implementation with no consumers

**Finding rule:** If during implementation any OTHER potential dead code or improvement is found, do NOT implement it. Register a Finding with: file, line, reason, impact, priority. That finding goes to a future PR.

## Dead Code Analysis

### Location

`src/apoch/modules/oracle/engine.py:285`

```python
if not isinstance(diag, dict):
    continue
```

### Why It Is Dead

1. `_apply_health()` receives `health: dict[str, Any]` — the parameter is always typed as dict
2. Called from line 214: `recs = [self._apply_health(r, health) for r in recs]`
3. The `health` parameter comes from Guardian's diagnostics, which always returns `dict[str, Any]` values at every key
4. Every value in the dict is always a dict, so `isinstance(diag, dict)` is always True
5. The `continue` branch is unreachable
6. Even if a value were not a dict, `diag.get("diagnostic", str(diag))` already handles non-dict values gracefully — the isinstance protection adds no value

## Acceptance Criteria

1. `isinstance(diag, dict)` check removed from `_apply_health()`
2. All existing tests pass without modification (behavior preserved)
3. Observable API unchanged — same input produces same output
4. Ruff clean — `ruff check` passes, `ruff format --check` passes
5. No new dead code introduced

## Test Plan

- Run full test suite excluding e2e: `uv run pytest tests/ -x -q --ignore=tests/e2e`
- No new tests needed unless existing tests specifically cover the dead `isinstance` check
- Verify no regressions in observable API behavior
