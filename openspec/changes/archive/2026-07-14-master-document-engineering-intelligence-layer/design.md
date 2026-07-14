# Design: Master Document — Engineering Intelligence Layer

## Narrative Approach

Single thread from §2 to §15. Each section answers one question, receives context from the previous, and passes refined context to the next. Concepts are introduced once in the earliest logical section and referenced (not redefined) thereafter.

```
§2 Vision ──→ §3 Philosophy ──→ §4 Goals ──→ §9 Modules ──→ §15 Criteria
  (why)         (how)            (what)       (with what)      (measure)
```

## Narrative Design Decisions

### Where is "Engineering Intelligence Layer" defined?
- **Choice**: §2 only. Never redefined. Later sections use "the Intelligence Layer" or "this vision."
- **Rationale**: Single canonical definition prevents drift.

### Where are the six dimensions introduced?
- **Choice**: §2 lists dimensions (memory, governance, observability, performance intelligence, optimization, reasoning). §9 maps to modules.
- **Rationale**: §2 = *what*, §9 = *who*. §9 references §2 — no repetition.

### How are modules framed?
- **Choice**: System responsibility first, implementation second.
- **Rationale**: Developer learns *what intelligence dimension* then *how it's implemented*. Existing text preserved.

### How does §4 reframe goals?
- **Choice**: One introductory sentence before the list. List unchanged.
- **Rationale**: Goals are correct. Framing explains they deliver an Intelligence Layer.

### How does §15 reframe criteria?
- **Choice**: One introductory sentence before the list. List unchanged.
- **Rationale**: Criteria describe functional completeness. Framing adds they define a complete Intelligence Layer.

## Narrative Flow

| Section | Question it answers | New concepts introduced | References from |
|---------|-------------------|------------------------|-----------------|
| §2 | Why does Apoch exist? | Engineering Intelligence Layer, six dimensions of intelligence | §1 (project overview) |
| §3 | How does it pursue that vision? | Intelligence as sixth principle, "structurally cannot provide" | §2 (Intelligence Layer) |
| §4 | What does it aim to achieve? | (none — reframes existing goals) | §2, §3 (vision + principles) |
| §9 | What capabilities and how do they cooperate? | Module-to-dimension mapping, inter-module data flow | §2 (six dimensions) |
| §15 | How do we know it's complete? | (none — reframes existing criteria) | §2, §3, §4, §9 (all prior sections) |

## Module System Responsibilities

Each module is described by its role in the Intelligence Layer, then by its implementation. The following is the *system-level framing* to add before each module's existing description:

| Module | Intelligence dimension | System responsibility | Consumes from | Provides to |
|--------|----------------------|----------------------|---------------|-------------|
| Chronicle | Persistent memory | Records and retrieves the project's institutional history | Agent events, tool calls | Oracle (context) |
| Guardian | Governance | Enforces project rules, architectural boundaries, and safe execution | Module lifecycle | All modules (policy) |
| Vision | Observability | Exposes runtime state, module health, and resource consumption | All modules | Operator, Optimizer |
| Pulse | Performance intelligence | Measures engineering productivity — cost, time, rework per feature | Agent activity | Optimizer (data) |
| Optimizer | Optimization | Detects improvement opportunities across project and process | Vision, Pulse, Chronicle | All modules (recommendations) |
| Oracle | Reasoning | Synthesizes data from all sources into architectural recommendations | Chronicle, Guardian, Vision, Pulse, Optimizer | Developer |

## Terminology Control

| Term | Introduced in | Usage rule |
|------|---------------|------------|
| "Engineering Intelligence Layer" | §2 (exactly once, defined) | After §2, use "the Intelligence Layer" or "this vision" |
| "six dimensions of intelligence" | §2 (list) | Referenced in §9 as "the dimensions introduced in §2" |
| Module names | §9 | Names used directly, no redefinition needed |
| "intelligence" (as philosophy) | §3 | Sixth verb in the philosophy list |

## Cohesion Validation

Before any text is written, validate:

- [ ] §2 and §9 do not both list the six dimensions — §9 references §2.
- [ ] "Engineering Intelligence Layer" appears verbatim only in §2.
- [ ] The agent relationship (augment, not replace) is stated in §2 and consistent in §3–§15.
- [ ] Each module's system responsibility (table above) matches its existing implementation description.
- [ ] No concept is defined more than once.
- [ ] No marketing language, no superlatives, no claims unbacked by architecture.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `README.md §2` | Add framing paragraph | Intelligence Layer definition (1 paragraph) |
| `README.md §3` | Add sixth verb + clarification | "Intelligence" dimension + structural value clarification |
| `README.md §4` | Add introductory sentence | Reframe goals as Intelligence Layer delivery |
| `README.md §9` | Add conceptual intro | 3-5 sentence introduction + module responsibility table |
| `README.md §15` | Add introductory sentence | Reframe criteria as Intelligence Layer completeness |
