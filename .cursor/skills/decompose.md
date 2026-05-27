# Skill: Request Decomposition
# File: .cursor/skills/decompose.md

> Algorithm for splitting a confirmed request into independent task cards.
> Used by: Decomposer
> Goal: produce the minimum number of cards that are independently implementable.

---

## Core principle

Split only when the split adds value.
Two cards are better than one only if they can be worked on independently
and each is clearer and more focused than the combined card would be.

Do not split for the sake of granularity.
Do not merge to avoid complexity.

---

## Algorithm

### Phase 1: Map the request

Read `request-NNN.md` completely. Build a mental map:

```
For each item in §scope (in scope):
  - What layer does it live in? (C++ core / Python bindings / tests / examples / docs)
  - What module does it touch?
  - Does it depend on any other item in this request?
  - What implementer type does it need?
```

### Phase 2: Group by independence

Group items that must be done together:
- Items that modify the same public symbol → same card
- Items that modify the same module's internal state → same card
- Items where B cannot compile without A → sequential cards with dependency

Separate items that can be done independently:
- Different layers with no shared symbols → separate cards
- Different modules with no shared headers → separate cards
- New functionality vs test coverage for it → separate cards (if test can be written independently)

### Phase 3: Apply size heuristic

Estimate each group:
- Small: < 1 day, < ~200 lines of change, single focused change
- Medium: 1-3 days, multiple related changes, one module
- Large: > 3 days, multiple modules, complex interactions

If a group is Large:
- Try to find a natural split point within it
- If no natural split exists — keep as one card and flag it as large
- Never split artificially just to reduce size

### Phase 4: Name each card

Each card needs a title that:
- Describes the change, not the implementation ("Add X to Y" not "Refactor module Z")
- Is unique within the project
- Can be used as a git branch slug: lowercase, hyphens, no spaces

Format: `<verb>-<subject>[-<qualifier>]`
Examples: `add-eval-cache`, `expose-phase-api-python`, `fix-deployment-determinism`

### Phase 5: Validate the decomposition

Before presenting to developer, check each card:

| Check | Question |
|---|---|
| Independence | Can this be implemented without waiting for another card? |
| Completeness | Does this card contain everything needed to implement it? |
| Clarity | Can the implementer understand what to do from this card alone? |
| Size | Is this implementable in a reasonable session? |
| Naming | Does the title describe the outcome, not the method? |

If any check fails — revise before presenting.

---

## Dependency notation

When card B depends on card A, state it explicitly:

```
task-002: expose-phase-api-python [Python] [small]
  depends on: task-001 (task-001 must be merged before task-002 begins)
```

Dependencies must be:
- Explicit — never implicit
- Directional — A → B, not circular
- Minimal — only state real dependencies, not "would be nice to have first"

---

## Common patterns in this project

**C++ change + Python bindings update**
Always two separate cards with explicit dependency.
Reason: different implementer types, different skills and rules.

**New feature + tests**
Prefer one card if the tests are tightly coupled to the feature.
Separate cards if the test suite can be written and reviewed independently.

**Refactoring + new functionality**
Always separate cards.
Reason: refactoring must not change behavior — mixing with new functionality
makes verification impossible.

**Multiple domain phases or modules touched**
Separate cards if the phases/modules are implemented independently.
One card if the change is a shared mechanism used by multiple phases/modules.
