# Tasks: Master Document — Engineering Intelligence Layer

## Global Rule: Normative Language

These terms MUST NOT be added, removed, or modified (typo corrections only):
- MUST, NEVER, ONLY, REQUIRED, FORBIDDEN, APPROVED
- "Version 1", "Roadmap", "Rules"
- Existing requirement strength (SHALL, SHOULD, MAY)

This change enriches strategic context, not normative level.

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

**Estimated changed lines**: ~50-80 additions, 0 deletions. Single PR.

## Phase 1: §2 Vision — Intelligence Layer Definition

- [ ] **1.1** Add framing paragraph after existing §2.
  - **Preserves**: Existing text verbatim.
  - **Adds**: 1 paragraph defining Apoch as an Engineering Intelligence Layer with six dimensions.
  - **Why**: Canonical identity for all subsequent sections.

## Phase 2: §3 Philosophy — Intelligence Dimension

- [ ] **2.1** Add "Intelligence" as sixth verb. Clarify structural value.
  - **Preserves**: Five verbs and order. Core principle "never reinvent."
  - **Adds**: "Intelligence" as sixth dimension. Clarification: value the agent structurally cannot provide for itself.
  - **Why**: Adds strategic purpose to tactical verbs.

## Phase 3: §4 Primary Goals — Strategic Framing

- [ ] **3.1** Add introductory sentence before goal list.
  - **Preserves**: All 7 goals verbatim.
  - **Adds**: One sentence framing goals as Intelligence Layer delivery.
  - **Why**: Reframes goals strategically, not as feature checklist.

## Phase 4: §9 Core Modules — Conceptual Introduction

- [ ] **4.1** Add conceptual intro before module list. (3-5 sentences)
  - **Preserves**: All per-module descriptions verbatim.
  - **Adds**: Introduction on 6-module composition. References §2 dimensions.
  - **Why**: Solves "why six modules?" and "how they work together."
  - **⚠️ Mandatory**: Cooperation as system property, NOT dependency requirement. Modules MUST remain independently installable (Rule 006). No "depends on," "requires," "needs." Use "can consume," "may provide data to," "integrates with."

## Phase 5: §15 Success Criteria — Strategic Framing

- [ ] **5.1** Add introductory sentence before criteria list.
  - **Preserves**: All 8 criteria verbatim.
  - **Adds**: One sentence framing criteria as Intelligence Layer completeness.
  - **Why**: Reframes functional completeness strategically.

## Phase 6: Coherence Verification

- [ ] **6.1** Validate narrative cohesion per design checklist.
  - §2 and §9 don't both list dimensions.
  - "Engineering Intelligence Layer" appears only in §2.
  - Agent relationship consistent across all sections.
  - No concept defined more than once.
  - Max +2 paragraphs per section.
  - Manual check: 7 validation questions answerable from document.
