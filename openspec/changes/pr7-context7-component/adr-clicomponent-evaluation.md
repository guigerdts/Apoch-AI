# ADR: CliComponent Abstraction Evaluation

**Date**: 2026-07-15
**Status**: Proposed (evaluation only — no implementation)
**Context**: Three real adapters exist (OpenSpec, Engram, Context7). Rule 2 (defer CliComponent until 2+ adapters) has been satisfied.

---

## 1. Raw Metrics

| File | Lines | Component logic lines¹ | Tests |
|------|-------|----------------------|-------|
| `openspec.py` | 332 | 307 | 41 |
| `engram.py` | 373 | 292 (+ 56 helpers) | 48 |
| `context7.py` | 299 | 274 | 36 |
| **Total** | **1004** | **873** | **125** |

¹ Excluding DESCRIPTOR (15 lines each) and parser (10 lines each). Engram helpers (56 lines) are genuine extra logic, not duplication.

---

## 2. Block-by-Block Duplication Analysis

### 2.1 Blocks that are 100% identical across all 3 adapters

| Block | Lines/file | ×3 total | Would move to base |
|-------|-----------|----------|-------------------|
| `__init__(self, runner)` | 3 | 9 | 3 |
| `descriptor` property | 3 | 9 | 3 |
| `activate()` body | 8 | 24 | 8 |
| `deactivate()` body | 4 | 12 | 4 |
| health() "not installed" return | 4 | 12 | 4 |
| **Subtotal** | **22** | **66** | **22** |

### 2.2 Blocks that are structurally identical (differ only by tool-specific strings)

These share the same control flow, error handling, and return shapes — only the tool name, command args, and registry IDs change.

| Block | Structure/file | Variation | Example | Would move to base |
|-------|---------------|-----------|---------|-------------------|
| `detect()` | ~24/32 lines | binary name, version flag, parser call | `shutil.which("openspec")` vs `shutil.which("ctx7")` | 24 |
| `install()` | ~18/40 lines | npm command (or platform dispatch) | `["npm", "install", "-g", "ctx7"]` | 18 |
| `verify()` | ~16/34 lines | check command | `["openspec", "doctor"]` vs `["ctx7", "--help"]` | 16 |
| `uninstall()` | ~12/28 lines | npm command (or platform dispatch) | `["npm", "uninstall", "-g", ...]` | 12 |
| **Subtotal** | **~70** | — | — | **70** |

### 2.3 Tool-specific logic (structural differences, NOT just data)

| Area | OpenSpec | Engram | Context7 |
|------|----------|--------|----------|
| **DESCRIPTOR** | 15 lines (data) | 15 lines (data) | 15 lines (data) |
| **Version parser** | 10 lines (data) | 10 lines (data) | 10 lines (data) |
| **detect() extras** | 8 lines (command, log prefix) | 8 lines (command, log prefix) | 8 lines (command, log prefix) |
| **install() extras** | 22 lines (version check) | 17 lines (platform dispatch via helpers) | 16 lines (npm cmd) |
| **verify() extras** | 12 lines (doctor cmd) | 14 lines (doctor cmd) | 14 lines (--help cmd) |
| **uninstall() extras** | 10 lines (npm cmd) | 28 lines (platform dispatch + path analysis + brew semantics) | 14 lines (npm cmd + npm sem) |
| **health()** | **62 lines** (JSON try/except + fallback) | **22 lines** (doctor exit code) | **28 lines** (detect-only) |
| **Helpers** | — | 56 lines (`_get_install_args`, `_get_uninstall_args`) | — |
| **Total tool-specific** | **139** | **170** | **107** |

### 2.4 Summary

```
Total component logic across 3 adapters:      873 lines
Structural (shared pattern, data/config):     276 lines (31.6%)
Logic differences (behavioral):               597 lines (68.4%)
  ├── health() alone:                         112 lines (12.8%)
  ├── Engram helpers:                          56 lines  (6.4%)
  ├── OpenSpec JSON health:                    40 lines  (4.6%)
  ├── Engram uninstall dispatch:               16 lines  (1.8%)
  └── All other diffs (install, verify, etc.):373 lines (42.7%)
```

**Critical finding**: The 276 "structural" lines could move to a base class. But 597 lines — 68% of the code — is genuinely tool-specific behavior, not just data configuration. And within those 597, **health() alone accounts for 112 lines of divergent logic**.

---

## 3. What a CliComponent Base Would Look Like

```python
class CliComponent(StackComponent):
    """Hypothetical base for CLI-based stack components."""

    # Provided by subclasses
    @property
    @abstractmethod
    def descriptor(self) -> StackDescriptor: ...

    @property
    @abstractmethod
    def binary_name(self) -> str: ...
    @property
    def version_args(self) -> list[str]:          # default ["--version"]
    @property
    def install_args(self) -> list[str] | None: ...
    @property
    def uninstall_args(self) -> list[str] | None: ...
    @property
    def verify_args(self) -> list[str]: ...
    @property
    def doctor_args(self) -> list[str] | None: ... # None = no doctor

    def parse_version(self, output: str) -> str | None:  # default regex

    # Hooks for structural variance
    def _on_uninstall_not_installed(self) -> OperationResult:  # success vs failure
    def _on_install_complete(self, info: ComponentInfo) -> OperationResult | None:
    def _health_check(self) -> dict:  # abstract — too divergent for default

    # Common implementations
    async def detect(self) -> ComponentInfo: ...
    async def activate(self) -> OperationResult: ...
    async def deactivate(self) -> OperationResult: ...
    async def install(self) -> OperationResult: ...
    async def verify(self) -> OperationResult: ...
    async def uninstall(self) -> OperationResult: ...
    # health() remains abstract
```

### 3.1 What a Base Class Saves

| Adapter | Current lines | Estimated with CliComponent | Lines saved |
|---------|--------------|----------------------------|-------------|
| OpenSpec | 332 | ~130 (DESCRIPTOR + parser + health + overrides) | ~202 |
| Engram | 373 | ~190 (DESCRIPTOR + parser + helpers + health + overrides) | ~183 |
| Context7 | 299 | ~110 (DESCRIPTOR + parser + health + overrides) | ~189 |
| **Base class** | — | ~90 | −90 (new) |
| **Total** | **1004** | **~520** | **~484 (48%)** |

### 3.2 What a Base Class Costs

1. **5 abstract properties + 3 abstract methods + 2 hooks** — that's the interface surface. Every new adapter must implement all of them.
2. **health() stays abstract** — with three completely different strategies (JSON try/except, exit code, detect-only), the base provides zero value for health. Each adapter still writes it from scratch.
3. **Engram's platform dispatch** doesn't fit the `install_args`/`uninstall_args` pattern cleanly — Engram needs to resolve args dynamically at call time based on `platform.system()` and `executable_path`.
4. **Different uninstall semantics** — the `_on_uninstall_not_installed` hook exists purely because Engram (brew) and OpenSpec/Context7 (npm) disagree on what "uninstall when absent" means.
5. **Indirection cost** — a developer debugging an adapter now traces through base class + overrides + hooks instead of reading one file top-to-bottom.

---

## 4. Decision Matrix

| Criterion | Metric | Value |
|-----------|--------|-------|
| % of code that is shared structural pattern | 276/873 | **31.6%** |
| % that would move to base class with data-only params | 276/873 | 31.6% |
| % that remains tool-specific after extraction | 597/873 | **68.4%** |
| health() divergence | 3 completely different strategies | High |
| Install divergence | 2 patterns (single cmd vs platform dispatch) | Medium |
| Uninstall divergence | 2 patterns (npm vs brew + path analysis) | Medium |
| Engram uniqueness | 56 lines of helpers (no equivalent in other 2) | Unique |

### Thresholds

| Threshold | Verdict |
|-----------|---------|
| **< 60% duplication** | ✅ **KEEP CURRENT DESIGN** |
| 60–80% duplication | Document pattern, wait for another adapter |
| > 80% duplication | Propose CliComponent in PR8 |

**Result: 31.6% shared structural code. Well below the 60% threshold.**

---

## 5. Verdict: KEEP CURRENT DESIGN

**Do NOT create CliComponent.**

### Reasoning

1. **31.6% duplication is too low** — The three adapters share structural patterns in only ~276 of 873 lines. The remaining 68% is genuinely tool-specific behavior (different health strategies, different install/uninstall mechanisms, platform dispatch unique to Engram).

2. **health() is irreconcilable** — Three completely different health strategies that share only the "not installed → down" preamble (4 lines). A base class would still require each adapter to implement health() from scratch.

3. **The abstraction would require 5+ abstract properties + 3 abstract methods + 2 hooks** — That's a complex interface for a 32% savings. Each new adapter pays the full interface cost regardless of whether it needs all those hooks.

4. **Engram is the outlier** — 56 lines of platform-dispatch helpers, different install strategy (brew/gobin), different uninstall strategy (path analysis), different uninstall semantics (success=False when absent). Engram would fight the abstraction at every point.

5. **Indirection over clarity** — Currently you read one file per component and the entire lifecycle is visible top-to-bottom. A base class splits the logic across two files, making debugging and onboarding harder for marginal gain.

### Risk of NOT abstracting

- The fourth adapter (if there is one) will add another ~300 lines of similar structure.
- If the fourth adapter follows the npm pattern (like OpenSpec + Context7), the duplication argument strengthens.
- If the fourth adapter is more like Engram (brew/gobin/ph平台 dispatch), the divergence argument strengthens.

**Recommendation**: Keep independent adapters. If a fourth adapter appears and is structurally similar to OpenSpec/Context7 (npm package, single install command, has doctor), re-evaluate at that point — the case for CliComponent becomes stronger at ~60%+ shared lines across 4 implementations.

### What to document instead

Rather than a base class, document the **Component Contract** informally:

> Every `apoch.stack` adapter MUST implement these 8 methods in this order:
> `__init__` → `descriptor` → `detect` → `install` → `verify` → `activate` → `deactivate` → `uninstall` → `health`
>
> Each method MUST:
> - Return the correct type (`ComponentInfo`, `OperationResult`, or `dict`)
> - Use `CommandRunner` via `self._runner`
> - Log errors with `log.warning()/log.error()` and include the tool name
> - Return `OperationResult(component="{id}", ...)` with the tool's registry ID
>
> Reference: `openspec.py` (Reference Component)

This contract is already followed by all three implementations naturally.

---

## 6. ADR Metadata

- **Approved by**: Evidence-based evaluation
- **Triggered by**: Rule 2 (wait for 2+ adapters before evaluating CliComponent)
- **Evidence**: Three real adapter implementations totaling 1,004 lines
- **Next review**: When a fourth adapter is implemented, or if an adapter exceeds 500 lines
