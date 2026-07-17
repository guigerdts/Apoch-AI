# ADR-007 — Concurrency Model

**Date:** 2026-07-14
**Status:** Approved
**Context:** The MCP Public API coordinator queries multiple modules to build a single tool response. Sequential queries would add unacceptable latency. The coordinator needs a concurrency model that is safe, predictable, and easy to reason about.

---

## 1. Objective

### 1.1 What this ADR guarantees

- Module queries run **in parallel** using `asyncio.gather()`.
- Each query has its own timeout (see ADR-004).
- One slow module does not block other modules from contributing.
- The coordinator never uses threads or processes — pure async concurrency.
- Module queries are **independent** — no module result depends on another module's result.

### 1.2 What is out of scope

- Distributed concurrency (single-process only).
- Rate limiting or backpressure (future concern).
- Database connection pooling (handled by individual modules).

---

## 2. Query Pattern

```python
queries: list[tuple[str, Coroutine, float]] = [
    ("vision", vision.module_state(), 1.0),
    ("guardian", guardian.all_diagnostics(), 0.5),
]

results = await self._query_modules(queries)
```

The `_query_modules` helper wraps each coroutine in `asyncio.wait_for()` with the specified timeout, collects all tasks via `asyncio.gather(return_exceptions=True)`, and maps results back to their module keys.

---

## 3. Safety Guarantees

- `CancelledError` propagates — if the asyncio event loop is cancelled, all queries are cancelled.
- Exceptions are caught per-query — one failing module does not affect others.
- Timeout errors return `None` for that module, not a crashed coordinator.
- Module queries are pure async functions — no shared state, no locks needed.

---

## 4. Consequences

- Adding a new module query is a one-line addition to the queries list.
- The total tool response time equals the SLOWEST module's response (or timeout), not the sum of all modules.
- `return_exceptions=True` ensures one `asyncio.TimeoutError` doesn't cascade.
