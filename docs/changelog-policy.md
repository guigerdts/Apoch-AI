# Changelog Policy

## Format

The CHANGELOG follows the [Keep a Changelog](https://keepachangelog.com/) convention. Every entry is written for humans, not machines — structured but readable.

## Versioning

This project adheres to [Semantic Versioning](https://semver.org/):

| Increment | When | Example |
|-----------|------|---------|
| MAJOR | Breaking API or behavior changes | `1.0.0` → `2.0.0` |
| MINOR | New features, backwards-compatible | `0.1.0` → `0.2.0` |
| PATCH | Bug fixes, no new features | `0.1.0` → `0.1.1` |

Pre-release versions use an `-alpha` suffix (e.g., `0.7.0-alpha`). During initial development (v0.x.x), MINOR increments can include breaking changes.

## Sections

Each release groups changes under these headings, in order:

| Section | Contents |
|---------|----------|
| **Added** | New features, commands, modules, adapters |
| **Changed** | Changes to existing behavior |
| **Deprecated** | Features scheduled for removal |
| **Removed** | Features removed in this release |
| **Fixed** | Bug fixes |
| **Security** | Vulnerability fixes |

Each entry references the PR that introduced it:

```markdown
### Added

- **CodeGraph Adapter** (`PR8`): Complete lifecycle with JSON health strategy.
  Detect, install, uninstall, verify, activate, deactivate, health — 31 tests.
```

## CHANGELOG Location

`/root/Apoch-AI/CHANGELOG.md`

## Current Version

`0.7.0-alpha` — see the CHANGELOG for the full release history.

## Conventions

- Entries are ordered by significance within each section
- Adapter/module names are in **bold**
- PR references link to GitHub PRs
- Breaking changes are called out explicitly under **Changed** or **Removed**
- Architecture decisions that affect multiple PRs get a dedicated subsection under **Architecture**
- No placeholders, no TODO entries, no unreleased sections with speculative content

## Release Cadence

No fixed schedule. Releases happen when meaningful functionality is complete and tests pass cleanly.
