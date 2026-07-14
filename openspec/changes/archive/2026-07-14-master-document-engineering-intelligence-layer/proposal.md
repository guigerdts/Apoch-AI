# Proposal: Master Document — Engineering Intelligence Layer

## Intent

The Master Document calls Apoch an "enhancement framework" — generic. A developer sees WHAT exists but not WHY or HOW modules compose into something greater.

**Objective**: Define Apoch's identity as an Engineering Intelligence Layer without modifying functional scope. No module changes responsibility. No new capabilities. Roadmap, architecture, rules untouched.

**Constraint**: "Engineering Intelligence Layer" is a strategic definition, not a product category. Original text preserved.

### Editing Principles
1. **Evolve, don't rewrite** — preserve original text; add framing only.
2. **Explain before extend** — clarify existing content first.
3. **No new capabilities** — modules keep current responsibilities.
4. **No responsibility changes** — Chronicle records, Guardian isolates, etc.
5. **Terminological consistency** — same terms across all sections.

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| §2 Vision — Engineering Layer framing | §10 Roadmap — frozen |
| §3 Philosophy — "intelligence" dimension | §11 Rules · §12 Methodology |
| §4 Goals — 2-3 intelligence capability goals | §13 Technology · §14 Principles |
| §9 Modules — conceptual intro on composition | No new modules, renames, removals |
| §15 Criteria — 2-3 capability-based criteria | Existing §9 descriptions preserved |

## Approach

**Strategic Evolution** per exploration:
1. Keep structure and existing text.
2. Add 1-2 paragraphs per section framing content as Intelligence Layer.
3. Each addition answers a question the document leaves open.
4. Objective language — no marketing, no superlatives.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Scope creep into roadmap/rules | Low | Enforce during review |
| Inconsistency §2↔§9 | Med | Conceptual intro bridges identity and implementation |
| Marketing language | Low | Architecture-grounded terms only |
| Document bloat | Low | Max +2 paragraphs per section |

## Rollback

`git checkout 448bfe2 -- README.md`. No code, data, or deps affected.

## Success Criteria

### Primary: Documentary Coherence
All touched sections (§2, §3, §4, §9, §15) describe the same product identity with consistent terminology. No contradictory framing.

### Secondary: Functional Scope
- Roadmap (§10), Rules (§11), Architecture (§13) unchanged
- Module responsibilities unchanged
- All original text preserved

### Validation Checklist (manual, not normative)
1. What is Apoch? · 2. Problem solved? · 3. Why not replace OpenCode? · 4. Unique? · 5. Why six modules? · 6. How they work together? · 7. Long-term vision?
