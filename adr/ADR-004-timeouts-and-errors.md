# ADR-004 — Timeouts & Error Codes

**Date:** 2026-07-14
**Status:** Approved
**Context:** The MCP Public API coordinator queries multiple modules in parallel. Each module may take arbitrarily long to respond, or fail entirely. The coordinator must bound its waiting time and produce a structured error response when modules are unavailable.

---

## 1. Objective

### 1.1 What this ADR guarantees

- Every module query has a configurable timeout.
- A module that exceeds its timeout is treated as `None` — the coordinator continues with remaining modules.
- If all modules timeout, the tool returns `ERR_TIMEOUT`.
- Error responses follow a standard format: `{"ok": false, "error": {"code": "ERR_...", "message": "..."}}`.

### 1.2 What is out of scope

- Retry logic (module queries run once per tool call).
- Circuit breakers (future concern for high-load scenarios).
- Per-module latency tracking.

---

## 2. Timeout Configuration

Default timeouts (in `ApochCoordinator._timeouts`):

| Module | Timeout |
|--------|---------|
| Vision | 1.0s |
| Guardian | 0.5s |
| Chronicle | 0.5s |
| Oracle | 2.0s |

Timeouts are configurable via the coordinator constructor (`timeouts` dict parameter).

---

## 3. Error Catalog

| Code | Meaning |
|------|---------|
| `ERR_TIMEOUT` | All modules timed out or failed |
| `ERR_DEPENDENCY_UNAVAILABLE` | Required module is not loaded or failed |
| `ERR_INVALID_ARGUMENT` | Invalid parameter value |
| `ERR_INTERNAL` | Unexpected internal error |
| `ERR_NOT_IMPLEMENTED` | Feature not implemented yet |

Defined in `apoch/public_api/errors.py`. The `error_response()` builder creates standardized error dicts.

---

## 4. Consequences

- Modules with slow startup (e.g., SQLite connections) may need higher timeouts in configuration.
- `ERR_TIMEOUT` is the only error that can occur at runtime under normal conditions.
