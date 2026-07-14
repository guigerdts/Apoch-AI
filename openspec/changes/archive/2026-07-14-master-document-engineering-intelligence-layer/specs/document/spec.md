# Document Specification: Master Document Identity Evolution

**Type**: Documentation-only evolution. No software capabilities added or modified.

**Critical constraint**: This change modifies identity, explanation, and purpose — NOT goals, NOT requirements, NOT success criteria, NOT commitments. Every existing goal, criterion, and requirement in the Master Document remains exactly as written. Only the framing around them evolves to reflect the Engineering Intelligence Layer identity.

## §2 Vision

### Must express
- Apoch is an Engineering Intelligence Layer, not a coding agent.
- It augments agents with capabilities they lack natively.
- Six dimensions: persistent memory, governance, observability, performance intelligence, optimization, architectural reasoning.

### Must not
- Claim Apoch replaces, competes with, or outperforms any agent.
- Introduce categories beyond "Engineering Intelligence Layer."
- Contradict §1 or existing vision paragraph.

### Constraints
- Original §2 text preserved verbatim. Framing paragraph only.

## §3 Philosophy

### Must express
- "Intelligence" as an additional dimension alongside the five verbs.
- Clarification: "provide value the agent structurally cannot provide for itself" (memory, governance, cross-session reasoning).

### Must not
- Remove or reorder existing five verbs.
- Change core principle "Never reinvent features that already exist inside the target agent."

### Constraints
- Original text preserved verbatim. Additions only.

## §4 Primary Goals — Clarification

### Must express
- The strategic purpose of existing goals through the Engineering Intelligence Layer lens.
- That each existing goal (simple install, native integration, modularity, cross-platform, DX, extensibility) serves the broader Intelligence Layer mission.

### Must not
- Add new functional goals.
- Remove, reorder, or rephrase existing goals.

### Constraints
- Existing goal list preserved verbatim.
- Clarification is framing text before or around the list, not new bullet items.

## §9 Core Modules — Conceptual Introduction

### Must express
- Each module covers one dimension of engineering intelligence.
- How modules relate conceptually (data flow, dependencies).
- Together they form a complete intelligence layer.

### Must not
- Change existing descriptions (Chronicle = event store, Guardian = exceptions, etc.).
- Reorder, rename, remove, or add modules.

### Constraints
- Introduction: 3-5 sentences before module list. Same style and tone.
- Original per-module text preserved verbatim.

### Module Relationship (input for Design)
- Chronicle → Oracle (historical context)
- Guardian → (policy enforcement boundary)
- Vision → all modules (runtime observability)
- Pulse → Optimizer (productivity data)
- Optimizer → all modules (improvement candidates)
- Oracle → all (architectural recommendations)

## §15 Success Criteria — Clarification

### Must express
- That the existing 8 success criteria remain the definition of "Version 1 complete."
- That those criteria, viewed through the Engineering Intelligence Layer lens, describe a complete intelligence platform — not just a functional framework.
- That documentation clarity is not a Version 1 success criterion but a validation outcome of this change itself.

### Must not
- Add new success criteria.
- Remove, reorder, or rephrase existing criteria.

### Constraints
- Existing §15 criteria list preserved verbatim.
- Clarification is framing text only (introductory sentence or paragraph).

## Cross-Section Consistency

| Requirement | All sections (§2, §3, §4, §9, §15) |
|-------------|--------------------------------------|
| "Engineering Intelligence Layer" | Same phrase, same meaning. No section redefines it differently. |
| Module names | Chronicle, Guardian, Vision, Pulse, Optimizer, Oracle — unchanged |
| Agent relationship | Apoch augments, does not replace — consistent everywhere |
| Tone | Technical, objective. No marketing language in any section |

## Out of Scope
§10 Roadmap · §11 Rules · §12 Methodology · §13 Technology · §14 Principles — not referenced in any spec or design artifact.
