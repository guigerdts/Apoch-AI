# Apoch-AI Benchmarks

> Measured on: Linux aarch64, Ubuntu 25.10, Python 3.14.6, uv 0.11.19, ruff 0.15.20
> Commit: `50ecb62` — `feat: PR3 — apoch_health end-to-end`
> Date: 2026-07-17

## Overview

Apoch-AI test suite: **1471 collected, 1463 passed, 8 skipped, 24 warnings**

| Metric | Value |
|---|---|
| Total test statements | 3779 |
| Coverage | 92.1% |
| Total suite time (serial) | ~140s |
| Slowest area | e2e (77.64s) |
| Fastest area | flat/core (8.24s) |

Coverage misses concentrate in error/recovery paths, CLI `--help` branches, and Pulse storage edge cases.

## Test Suite Composition

### By Area

| Area | Collected | Passed | Skipped | Time (s) | Coverage | Notes |
|---|---|---|---|---|---|---|
| `tests/public_api/` | 324 | 324 | 0 | 10.24 | 96.2% (coordinator) | Coordinator wiring, models, errors, metrics |
| `tests/stack/` | 401 | 401 | 0 | 12.59 | 91–100% | Manager, registry, lock, manifest, components |
| `tests/modules/` | 391 | 391 | 0 | 11.32 | 80.8–100% | Vision, Oracle, Guardian, Optimizer, Pulse, Chronicle |
| `tests/e2e/` | 51 | 43 | 8 | 77.64 | N/A | CodeGraph, Context7, Engram, OpenSpec infrastructure |
| `tests/test_e2e_mcp.py` | 10 | 10 | 0 | 9.89 | N/A | MCP protocol E2E |
| `tests/test_integration_pr2.py` | 14 | 14 | 0 | 10.42 | N/A | PR2 integration |
| Root flat tests (17 files) | 280 | 280 | 0 | 8.24 | 88–100% | Adapters, engine, events, CLI, config, registry |

### By Module (tests/modules/)

| Module | Tests |
|---|---|
| pulse | 133 |
| optimizer | 99 |
| oracle | 89 |
| chronicle | 35 |
| guardian | 25 |
| vision | — (included in 391 total) |

### By Stack Component (tests/stack/)

| Component | Tests |
|---|---|
| components/ (4 MCP adapters) | 109 |
| test_manager | 56 |
| test_isolation | 34 |
| test_cli_stack | 27 |
| test_downloader | 25 |
| test_integration_flow | 19 |
| test_events | 18 |
| test_registry | 16 |
| test_lock | 15 |
| test_state | 10 |
| test_manifest | 10 |
| test_errors | 10 |
| test_clock | 8 |
| test_descriptor | 5 |
| test_component | 4 |
| test_runner | 4 |
| test_paths | 2 |
| test_result | 2 |
| test_factory | 1 |

## Coverage Report

```
Name                                              Stmts   Miss  Cover
---------------------------------------------------------------------
src/apoch/__init__.py                                54      0 100.0%
src/apoch/adapter_manager.py                        247      2  99.2%
src/apoch/adapters/__init__.py                        3      0 100.0%
src/apoch/adapters/engine.py                        137      0 100.0%
src/apoch/adapters/opencode.py                       43      0 100.0%
src/apoch/adapters/opencode_install.py               11      0 100.0%
src/apoch/adapters/opencode_mcp.py                    2      0 100.0%
src/apoch/cli/__init__.py                             2      0 100.0%
src/apoch/cli/cli.py                                 96      1  99.0%
src/apoch/cli/doctor.py                              47      1  97.9%
src/apoch/cli/eil.py                                 22      0 100.0%
src/apoch/cli/install.py                             33      0 100.0%
src/apoch/cli/mcp.py                                  8      0 100.0%
src/apoch/config.py                                 158      0 100.0%
src/apoch/engine.py                                  32      0 100.0%
src/apoch/events.py                                  18      0 100.0%
src/apoch/exceptions.py                              43      0 100.0%
src/apoch/modules/__init__.py                         6      0 100.0%
src/apoch/modules/chronicle/__init__.py              10      0 100.0%
src/apoch/modules/chronicle/models.py                19      0 100.0%
src/apoch/modules/chronicle/module.py                88      0 100.0%
src/apoch/modules/chronicle/storage.py               70      1  98.6%
src/apoch/modules/guardian/__init__.py                9      0 100.0%
src/apoch/modules/guardian/models.py                 14      0 100.0%
src/apoch/modules/guardian/module.py                 62      1  98.4%
src/apoch/modules/optimizer/__init__.py              10      0 100.0%
src/apoch/modules/optimizer/detectors.py             42      0 100.0%
src/apoch/modules/optimizer/models.py                11      0 100.0%
src/apoch/modules/optimizer/module.py               165      1  99.4%
src/apoch/modules/oracle/__init__.py                 14      0 100.0%
src/apoch/modules/oracle/engine.py                   69      0 100.0%
src/apoch/modules/oracle/models.py                   11      0 100.0%
src/apoch/modules/oracle/module.py                  191     13  93.2%
src/apoch/modules/pulse/__init__.py                   7      0 100.0%
src/apoch/modules/pulse/analysis.py                 113      8  92.9%
src/apoch/modules/pulse/models.py                    43      0 100.0%
src/apoch/modules/pulse/module.py                    61      0 100.0%
src/apoch/modules/pulse/storage.py                   98     11  88.8%
src/apoch/modules/vision/__init__.py                  9      5  44.4%
src/apoch/modules/vision/models.py                   20      0 100.0%
src/apoch/modules/vision/module.py                  125     24  80.8%
src/apoch/public_api/__init__.py                      2      0 100.0%
src/apoch/public_api/coordinator.py                 522     20  96.2%
src/apoch/public_api/errors.py                       21      0 100.0%
src/apoch/public_api/metrics.py                      13      0 100.0%
src/apoch/public_api/models.py                       52      0 100.0%
src/apoch/public_api/registry.py                     10      0 100.0%
src/apoch/public_api/version.py                       2      0 100.0%
src/apoch/stack/__init__.py                          16      0 100.0%
src/apoch/stack/clock.py                             15      0 100.0%
src/apoch/stack/component.py                         36      0 100.0%
src/apoch/stack/components/__init__.py                4      0 100.0%
src/apoch/stack/components/codegraph.py              91      0 100.0%
src/apoch/stack/components/context7.py               82      0 100.0%
src/apoch/stack/components/engram.py                110      2  98.2%
src/apoch/stack/components/openspec.py               98      0 100.0%
src/apoch/stack/descriptor.py                        22      0 100.0%
src/apoch/stack/downloader.py                        64      5  92.2%
src/apoch/stack/events.py                            17      0 100.0%
src/apoch/stack/exceptions.py                        11      0 100.0%
src/apoch/stack/factory.py                            7      0 100.0%
src/apoch/stack/lock.py                              60      6  90.0%
src/apoch/stack/manager.py                          177     16  91.0%
src/apoch/stack/manifest.py                          53      5  90.6%
src/apoch/stack/paths.py                             39      0 100.0%
src/apoch/stack/registry.py                          49      3  93.9%
src/apoch/stack/result.py                             9      0 100.0%
src/apoch/stack/runner.py                            45      0 100.0%
src/apoch/stack/state.py                             42      0 100.0%
---------------------------------------------------------------------
TOTAL                                               3779    297  92.1%
```

### Lowest Coverage Modules

| Module | Cover | Uncovered Lines |
|---|---|---|
| `vision/__init__.py` | 44.4% | 16–21 |
| `vision/module.py` | 80.8% | Recovery paths, degraded states |
| `pulse/storage.py` | 88.8% | Edge cases in persistence |
| `stack/lock.py` | 90.0% | Timeout/contention paths |
| `stack/manifest.py` | 90.6% | Error handling branches |
| `stack/manager.py` | 91.0% | 72–73, 109, 254–261, 326–332, 423–431 |
| `stack/downloader.py` | 92.2% | 96, 100–102, 117 |
| `pulse/analysis.py` | 92.9% | 90–93, 102, 105, 111, 262, 271 |
| `stack/registry.py` | 93.9% | 99, 109–110 |
| `oracle/module.py` | 93.2% | Error/recovery branches |

## Performance Characteristics

### Per-Area Timing

| Area | Wall Time | User | System | Tests/sec |
|---|---|---|---|---|
| public_api | 10.24s | 2.37s | 1.01s | 31.6 |
| stack | 12.59s | 3.50s | 1.40s | 31.9 |
| modules | 11.32s | 2.90s | 1.40s | 34.5 |
| e2e | 77.64s | 33.81s | 16.53s | 0.66 |
| flat/core | 8.24s | 5.34s | 1.63s | 34.0 |
| e2e_mcp | 9.89s | 4.17s | 1.19s | 1.01 |
| integration_pr2 | 10.42s | 4.62s | 1.56s | 1.34 |

### Latency Expectations (Public API Tools)

| Tool | Avg Time | Notes |
|---|---|---|
| `apoch_vision_*` | <50ms | In-memory state queries, no I/O |
| `apoch_guardian_*` | <50ms | In-memory diagnostics, cleared per call |
| `apoch_chronicle_*` | <5ms (record), <50ms (query) | SQLite-backed |
| `apoch_health` | <100ms | Aggregate across modules |

E2e tests dominate runtime because they exercise real MCP server startup/shutdown, network I/O to CodeGraph/Context7/Engram/OpenSpec indices, and CLI subprocess spawning.

## Platform Support Matrix

| Component | Linux (aarch64) | Notes |
|---|---|---|
| Python | 3.14.6 | Primary target |
| uv | 0.11.19 | Package/project management |
| ruff | 0.15.20 | Linting & formatting |
| pytest | (uv-managed) | Test runner |
| pytest-cov | (uv-managed) | Coverage |
| All tests | ✅ 1463 / 1471 | 8 skipped (e2e MCP-dependent) |

## CI/CD Status

- Pre-commit: ruff lint + format check
- Test runner: `uv run pytest` 
- Coverage gate: 92.1% (target >90%)
- Slowest CI step: e2e tests (~78s)
- Fastest CI step: unit tests per area (~10–13s each)

## Skipped Tests

8 tests skipped across the suite — all in `tests/e2e/`. These require external MCP servers (CodeGraph, Context7, Engram, OpenSpec) that are unavailable in the benchmark environment. They pass in CI where those services are connected.
