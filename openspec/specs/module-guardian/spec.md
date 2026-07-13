# Module: Guardian Specification

## Objective

Protect the Apoch-AI Core from misbehaving modules by enforcing execution boundaries, isolating exceptions, and applying configurable policies. Guardian is the system's safety net — it ensures one module cannot compromise the stability of others.

## Responsibilities

- Wrap module lifecycle calls in exception boundaries
- Capture and classify exceptions from module code
- Isolate crashes so they never propagate to the Core or other modules
- Enforce configurable policies (timeouts, resource limits, allowed operations)
- Provide diagnostics data after a module failure (what happened, stack trace, module state)
- Log all enforcement actions via Chronicle for auditability

## Scope

### In Scope
- Exception boundary around every module lifecycle call (`init`, `start`, `stop`, `shutdown`)
- Module state machine tracking: `loaded → running → stopped → shutdown` with `failed` as error state
- Configurable timeout per lifecycle phase (default: 30s start, 10s stop)
- Policy definition and enforcement (what modules MAY do)
- Post-failure diagnostics captured and logged
- Graceful degradation: Guardian itself MUST NOT be a single point of failure

### Out of Scope
- OS-level process isolation (containers, namespaces)
- Memory or CPU resource limiting (future)
- Network access control (future)
- Policy compiler or DSL (policy is code in v1)

## Architecture

Guardian wraps each module instance in a proxy that intercepts lifecycle calls. Before invoking a module method, Guardian checks timeout, state, and policy. If any check fails, the exception is captured, module transitions to `failed`, and diagnostics are recorded.

```
Core → GuardianProxy(module) → check policy → call module.start()
                                                     │
                                              [success] → running state
                                              [exception] → failed state + diagnostics
```

Guardian's own operations MUST use minimal dependencies and MUST handle their own errors silently (log and continue).

## Public Interfaces

### Guardian API

```python
class Guardian:
    async def protect(self, module: Module, call: str, timeout: float) -> Any: ...
    async def diagnostics(self, module_name: str) -> ModuleDiagnostics: ...
    def set_policy(self, module_name: str, policy: Policy) -> None: ...
    def state(self, module_name: str) -> ModuleState: ...
    def all_states(self) -> dict[str, ModuleState]: ...
```

### Types

```python
class ModuleState(Enum):
    LOADED = "loaded"
    RUNNING = "running"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"
    FAILED = "failed"

@dataclass
class ModuleDiagnostics:
    module_name: str
    current_state: ModuleState
    last_error: str | None
    last_error_traceback: str | None
    fail_count: int
    uptime_seconds: float | None
```

## Dependencies

- **Internal**: Module ABC, Chronicle (log enforcement actions), Vision (diagnostic logging)
- **External**: Python stdlib `asyncio` (timeout handling), `traceback` (stack capture)

## Requirements

### Requirement: Exception Isolation

Guardian MUST catch any exception raised during a module's lifecycle call and prevent it from propagating to the caller.

#### Scenario: Module raises during start

- GIVEN a module whose `start()` raises `ValueError("invalid config")`
- WHEN the Core calls `module.start()` through Guardian's protection
- THEN Guardian MUST catch the ValueError
- THEN the module MUST transition to `failed` state
- THEN the Core MUST NOT receive the ValueError
- AND other modules MUST continue unaffected

#### Scenario: Module raises during stop

- GIVEN a module whose `stop()` raises `RuntimeError`
- WHEN Guardian's protection wraps the stop call
- THEN Guardian MUST catch the exception
- THEN the module MUST transition to `failed` (or stay `stopped` if already partially stopped)
- AND `shutdown()` MUST still be called after the failed stop

#### Scenario: Uncaught exception in module-initiated async task

- GIVEN a module that spawns an asyncio task that later raises unhandled
- WHEN that task raises
- THEN Guardian SHOULD capture the exception via a module-provided exception handler
- AND the module SHOULD be marked as `failed`
- AND the Core MUST NOT crash

### Requirement: State Machine

Guardian MUST track each module's lifecycle state and reject invalid transitions.

#### Scenario: Valid transition loaded → running

- GIVEN a module in `loaded` state after `init()`
- WHEN `start()` completes successfully
- THEN Guardian MUST set state to `running`

#### Scenario: Invalid transition stopped → start

- GIVEN a module in `stopped` state
- WHEN `start()` is called again without going through `init`
- THEN Guardian MUST reject with `StateTransitionError`
- AND the module MUST remain in `stopped`

#### Scenario: Diagnostics after failure

- GIVEN a module that failed with an exception during `start()`
- WHEN `guardian.diagnostics("chronicle")` is called
- THEN the result MUST include the exception type, message, traceback, and state `failed`
- AND `fail_count` MUST be >= 1

### Requirement: Policy Enforcement

Guardian SHOULD enforce configurable policies per module and reject calls that violate them.

#### Scenario: Timeout policy violated

- GIVEN a module with a `start` timeout policy of 5 seconds
- WHEN the module's `start()` takes 10 seconds
- THEN Guardian MUST raise `TimeoutError` inside the boundary
- THEN the module MUST transition to `failed`
- AND the timeout MUST be logged via Chronicle

#### Scenario: No policy defined for module

- GIVEN a module with no explicit policy
- WHEN Guardian checks policy before a lifecycle call
- THEN Guardian MUST apply the default policy (30s start, 10s stop)
- AND the call MUST proceed

## Error Cases

| Condition | Behavior |
|-----------|----------|
| Guardian itself raises an exception | Log the Guardian failure, do not wrap it — Guardian failure is a Core failure |
| Module timeout | Module set to `failed`; diagnostics captured; module start retried on next startup |
| Invalid state transition | `StateTransitionError` raised to caller; state unchanged |
| Policy check on unknown module | Apply default policy; log warning |

## Acceptance Criteria

- [ ] Module exception in any lifecycle call is caught and does not crash Core
- [ ] State machine rejects `start()` on a module already in `running`
- [ ] Diagnostics endpoint returns correct error info after failure
- [ ] Timeout enforcement works: a module that sleeps 60s with 5s timeout is marked failed after 5s
- [ ] Guardian's own failure is a distinct, observable event (not silently hidden)
- [ ] `guardian.all_states()` returns correct state for all loaded modules

## Risks

| Risk | Mitigation |
|------|------------|
| Module hangs in `stop()` and blocks shutdown | Guardian timeout on `stop`; `shutdown()` called regardless |
| Guardian's own exception masking real bugs | Guardian logs every action; diagnostics preserve original traceback |
| Timeout too aggressive for cold-start modules | Timeouts are configurable per module; defaults are conservative |

## Future Considerations

- Retry policies for transient module failures (circuit breaker)
- Module quarantine after N failures (disable automatically)
- Policy-as-data with runtime reload
- Sandboxed subinterpreters for module execution isolation (Python 3.13+)
