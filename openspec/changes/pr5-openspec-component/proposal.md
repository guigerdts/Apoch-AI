# PR5 — OpenSpec Stack Component Proposal

## Intent
Integrate OpenSpec as the first real `apoch stack` component. Apoch does NOT implement OpenSpec — it acts as an adapter to the official project via its public CLI. This component serves as the **architectural template** for Engram, Context7, and CodeGraph.

## Core Stack Philosophy (MANDATORY — ALL components)
Apoch does NOT implement any component. It only acts as an adapter to each official project using its public interface. All project-specific information (install command, URLs, version detection, prerequisites) must come from the official project — never hardcoded from assumptions.

## Architectural increments to StackDescriptor (model update)
- **id**: str — Stable identifier (e.g. "openspec")
- **install_command**: str — Exact official install command
- **install_manager**: str — Package manager name (e.g. "npm")
- **homepage**: str — Project homepage URL
- **repository**: str — Source repository URL
- **docs_url**: str — Documentation URL
- **requires**: tuple[str, ...] — Prerequisite specs

## Architectural increments to ComponentInfo (model update)
- **available_version**: str | None — Latest available version (for OUTDATED detection)

## Architectural increments to StackComponent ABC (model update)
- **health()**: abstract async method — functional check beyond existence/version

## Files (PR5)
- MODIFY `src/apoch/stack/descriptor.py` — model updates
- MODIFY `src/apoch/stack/component.py` — ComponentInfo + health()
- CREATE `src/apoch/stack/components/openspec.py` — OpenSpecComponent
- MODIFY `src/apoch/stack/components/__init__.py` — export
- MODIFY `pyproject.toml` — entry point
- CREATE `tests/stack/components/test_openspec.py`
- UPDATE `openspec/specs/core-stack/spec.md`
- UPDATE `openspec/changes/core-stack-installation/design.md`

## Dependencies
apoch.stack (existing)

## Risks
- Node.js/npm availability → clear error messages + requires field
- CLI output format changes → robust parser with logging, never crashes
- npm network/permissions → handled by OperationResult
