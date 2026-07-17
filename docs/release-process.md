# Release Process

## Versioning

Apoch-AI follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).

| Increment | When |
|-----------|------|
| MAJOR | Breaking API or behavior changes |
| MINOR | New features in a backwards-compatible manner |
| PATCH | Bug fixes and small corrections |

Pre-release labels use `-alpha` suffix (e.g., `0.9.0-alpha`).

## Release Checklist

- [ ] All tests pass: `uv run pytest`
- [ ] Ruff checks pass: `uv run ruff check src/ tests/`
- [ ] Ruff format would produce no changes: `uv run ruff format --check src/ tests/`
- [ ] `CHANGELOG.md` updated with all changes since last release
- [ ] Version bumped in `src/apoch/__init__.py` and `pyproject.toml`
- [ ] `uv build` succeeds
- [ ] Tag created: `git tag v<version> && git push origin v<version>`
- [ ] Milestone closed on GitHub
- [ ] Release notes drafted from CHANGELOG entries

```bash
# Tagging a release
git tag v0.9.0-alpha
git push origin v0.9.0-alpha
```

## Current Release

| Attribute | Value |
|-----------|-------|
| Version | `0.9.0-alpha` |
| Status | Alpha — active development |
| CHANGELOG | `/root/Apoch-AI/CHANGELOG.md` |
| Milestone | #1 — Ecosystem Adapters (all 4 adapters implemented, Core Stack stable) |

## Branch Model

```
main               # Stable — all merges land here
├── feature/*      # Feature branches (short-lived)
├── chained-pr/*   # Stacked PR chains (e.g., chained-pr/pr5.1 → pr5.2)
```

- `main` is always releasable
- Feature branches branch from `main` and merge via PR
- Chained PRs stack against `main` and merge in order
- No long-lived branches

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| #1 | Ecosystem Adapters — 4 adapters, Core Stack stable | ✅ Complete |
| #2 | Core Modules — Oracle, Pulse, Optimizer | ⏳ In progress |

Milestones are tracked on GitHub at `https://github.com/guigerdts/Apoch-AI/milestones`.
