# Design: PR-2 — Dead Code Removal

## Technical Approach

Single-line deletion. Remove the unreachable `isinstance(diag, dict)` guard from `_apply_health()` in `RecommendationEngine`. The check was always True because Guardian diagnostics always return `dict[str, Any]` values.

## Architecture Decisions

No architectural changes. No contract changes.

| Decision | Rationale |
|----------|-----------|
| Remove only the guard, not the `diag.get` call | `diag.get("diagnostic", str(diag))` is a valid defensive get on a dict — removing the `isinstance` does not affect it |
| No new tests | The removed code was unreachable — no existing test could exercise it, so no test needs updating |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Behavioral change | None | N/A | The removed branch was unreachable — the same `continue`-free path always executed |
| Lint/format failure after edit | Low | Trivial | `ruff check` + `ruff format --check` as verification step |
| Other dead code discovered | Medium | Informational | Register as Finding for future PR — do not fix now |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/modules/oracle/engine.py` | Modify | Remove `if not isinstance(diag, dict): continue` (line 285–286) |
