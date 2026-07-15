# Contributing Guide

## PR Workflow

Every change follows the SDD (Spec-Driven Development) flow:

```
Proposal → Spec → Design → Tasks → Apply → Verify → Archive
```

No implementation without an approved specification. Each phase produces an artifact in `openspec/changes/<change-name>/`.

## Chained PRs

Apoch-AI uses a **stacked-to-main** chained PR strategy:

```
Foundation PR     → Component PR
   (e.g. PR5.1)        (e.g. PR5.2 → PR5.3)
```

| Rule | Detail |
|------|--------|
| Base | All chains target `main` |
| Size | Each PR under 400 lines |
| Order | Foundation first, then lifecycle methods |
| Rollback | Every PR must have a clear rollback boundary |
| Naming | `PR<N>.<M>: <description>` (e.g., `PR5.1: Foundation — OpenSpec component`) |

For large changes, split into **force-chained** PRs that must merge in order.

## Governance Rules

### Core Stack Freeze Rule

No modifications to `StackComponent`, `StackManager`, `StackState`, `StackRegistry`, or the `CommandRunner` hierarchy. The 8 files in `src/apoch/stack/`:

| File | Role |
|------|------|
| `component.py` | `StackComponent` ABC + `ComponentInfo` |
| `descriptor.py` | `StackDescriptor` |
| `manager.py` | `StackManager` orchestrator |
| `state.py` | `StackState` FSM (11 states) |
| `result.py` | `OperationResult` |
| `runner.py` | `CommandRunner` / `RealRunner` / `MockRunner` |
| `registry.py` | `StackRegistry` |
| `exceptions.py` | Stack-specific exceptions |

New capabilities arrive only through the Adapter Layer — never by modifying core files.

### Reference Component Rule

OpenSpec is the reference component. All adapter implementations must mirror its structure:
- Same 8 lifecycle methods in the same order
- Same import structure
- Same error message patterns
- Same test organization (class per lifecycle method)

Structural differences require documented CLI limitation justification.

### CliComponent Evaluation

The current ADR keeps the CliComponent design. Shared code between adapters is at 31.6% — refactoring into a shared base is not justified.

## SDD Artifact Structure

```
openspec/
├── config.yaml           # Project-wide SDD config
├── specs/                # Approved specifications
│   ├── core-stack/
│   ├── module-chronicle/
│   └── ...
└── changes/              # Active/archived changes
    ├── pr5-openspec-component/
    ├── pr6-engram-component/
    ├── pr7-context7-component/
    ├── pr8-codegraph-component/
    └── archive/          # Completed changes
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Descriptor constant | UPPER_CASE with `_DESCRIPTOR` suffix | `CODEGRAPH_DESCRIPTOR` |
| Private helpers | `_` prefix + snake_case | `_parse_version()` |
| Test classes | `Test<Name>` | `TestDetect`, `TestInstall` |
| Test methods | `test_<scenario>` | `test_not_installed_when_binary_missing` |
| Component class | `<Name>Component` | `CodeGraphComponent` |
| Module class | `<Name>Module` | `ChronicleModule` |

## Code Style

- Follow the patterns in existing components — consistency over cleverness
- No new abstractions without documented justification (e.g., why a shared base class is needed)
- All external calls go through `CommandRunner` — components never execute subprocesses directly
- Zero cross-imports between adapter implementations

## Testing Requirements

| Requirement | Detail |
|------------|--------|
| Coverage | All 8 lifecycle methods need tests |
| Mocking | `MockRunner` + `monkeypatch` for all external calls |
| Edge cases | Version parsing, binary not found, CLI errors, absent-on-uninstall |
| Isolation | Each test creates its own component instance with injected runner |

## Structural Comparison

Before merging any new adapter, verify method order matches OpenSpec:

```bash
grep -n "^    async def\|^    @property" src/apoch/stack/components/openspec.py
grep -n "^    async def\|^    @property" src/apoch/stack/components/my_tool.py
```

## Rollback

Every chained PR must have a clear rollback boundary documented in its proposal. Rollback is either:
- **Revert the PR** — if the change is fully contained in a single merge
- **Sequence rollback** — for force-chained PRs, revert in reverse merge order
