# loop-design.md
# Design Loop — Architect + Planner + Critic

> Rules for Phase 2 of the pipeline.
> Read this file if you are Architect, Planner, or Critic.
> Authoritative flow is in `pipeline.md`. This file defines the loop mechanics.
>
> Key properties of this loop:
> - Deadlock rule: if no progress after 3 iterations — stop and surface to developer.
> - Critic re-evaluates from scratch each iteration, not only the changed parts.
> - [QUESTION] stops the loop — agents do not guess answers, they ask.
> - Unified session log with iteration markers — developer sees what is happening at any time.

---

## Purpose

The design loop produces an approved, conflict-free plan before any implementation begins.
It is iterative: agents cycle until all blocking issues are resolved.
No agent proceeds to Phase 3 until the stop condition is met and the developer approves at CP2.

---

## Participants

| Agent | Role in loop |
|---|---|
| Architect | Makes and owns architectural decisions. Revises when Critic raises arch issues. |
| Planner | Produces and owns the step-by-step plan. Revises when Critic raises plan issues. |
| Critic | Attacks plan and architecture. Returns feedback. Agrees when no blockers remain. |

---

## Loop flow

```
Architect produces §architecture
        |
        v
Planner produces plan draft
        |
        v
Critic reviews plan draft
        |
   [BLOCKING issues?]
        |
   yes  |  no
   _____|_____
  |           |
  v           v
Critic    Critic signals AGREE
feedback       |
  |            v
  |     [arch issues in feedback?]
  |            |
  |       yes  |  no
  |       _____|_____
  |      |           |
  v      v           v
Planner  Architect  → stop condition met
revises  revises       write clean artifacts
plan     §arch         → CP2
  |      |
  |______| (loop back to Planner)
```

---

## Iteration rules

- Each iteration is appended to `sessions/task-NNN-plan.md` with a clear iteration marker.
- Architect and Planner must address every [BLOCKING] issue before the next Critic pass.
- Critic must re-evaluate from scratch each iteration — not just the changed parts.
- Maximum iterations: not fixed. Loop continues until stop condition is met.
  If no progress after 3 iterations — surface the deadlock to the developer.
- [WARNING] issues do not block loop completion. They are recorded and passed forward.

---

## Feedback classification

Critic classifies every issue before returning feedback:

| Severity | Meaning | Effect |
|---|---|---|
| [BLOCKING] | Must be resolved before plan can proceed | Loop continues |
| [WARNING] | Should be addressed but does not block | Recorded, loop may complete |
| [QUESTION] | Needs clarification — from developer or architect | Pause loop, ask |

If Critic raises a [QUESTION] that cannot be answered within the loop — stop the loop
and surface the question to the developer before continuing.

---

## Stop condition

The loop stops when ALL of the following are true:

- Architect confirms: no unresolved architectural concerns in the current plan.
- Planner confirms: no unresolved gaps or ambiguities in the step sequence.
- Critic confirms: zero [BLOCKING] issues remain.

When stop condition is met:
1. Write clean plan to `tasks/decisions/task-NNN-plan.md`
2. Update `task-NNN.md §plan` with the final version
3. Update `task-NNN.md Status:` to `design-awaiting-CP2` (Critic responsibility)
4. Call Memory writer if architectural decisions were made or revised
5. Stop and surface output for developer review — CP2

---

## Status transitions in this loop

Each agent updates `Status:` in the task card at each transition.
Full vocabulary is in `pipeline.md §6`.

| Transition | Who sets it | Value |
|---|---|---|
| Architect begins writing §architecture (initial or revised) | Architect | `architecture-in-progress` |
| §architecture complete, passed to Planner | Architect | `architecture-ready` |
| Planner begins writing plan draft | Planner | `planning` |
| Plan draft written, passed to Critic | Planner | `planned` |
| Critic begins evaluating (each iteration) | Critic | `design-in-progress` |
| Loop stop condition met | Critic | `design-awaiting-CP2` |
| Escalation stops the loop | whichever agent detects it | `impl-blocked` |

---

## What Critic must challenge

Critic is required to evaluate every plan against all of the following:

- Completeness: are all steps of the plan specified? Are there missing cases?
- Feasibility: can each step be implemented given the architectural constraints?
- Architecture compliance: does the plan violate any invariant in `.cursor/memory/architecture/map.md`?
- Risk coverage: are performance, ABI, determinism, and ownership risks identified?
- Dependency correctness: are all affected symbols, bindings, and tests accounted for?
- Test coverage: does the plan produce code that can be verified by the test criteria?

Critic must not approve a plan that has any [BLOCKING] issue in the above categories.

---

## What Architect must produce

The `§architecture` section of the task card must contain:

- Affected modules and their boundaries
- New or changed interfaces (with ABI impact if public)
- Patterns and constraints to follow during implementation
- Explicit list of what must NOT be changed (invariants)
- References to relevant ADRs in `.cursor/memory/decisions/adr-log.md`

If the plan reveals that an architectural decision needs revision —
Architect updates `§architecture` and appends to `.cursor/memory/architecture/map.md`.
Every such revision is a candidate for a new ADR entry.

---

## Session file format for this loop

```markdown
# Session: task-NNN — design loop

## Iteration 1 — [Architect]
### §architecture draft
<decisions, affected modules, constraints>

## Iteration 1 — [Planner]
### plan draft
<step-by-step plan>

## Iteration 1 — [Critic]
### review
[BLOCKING] <issue>
[WARNING] <issue>
[QUESTION] <question>

## Iteration 2 — [Architect]
### revised §architecture (if changed)
<what changed and why>

## Iteration 2 — [Planner]
### revised plan
<what changed and why>

## Iteration 2 — [Critic]
### review
<re-evaluation from scratch>

## Agreed — iteration N — [Critic]

### Stop condition confirmed
- Architect: no unresolved concerns
- Planner: no unresolved gaps
- Critic: zero [BLOCKING] issues

### Remaining [WARNING] items
<list — passed forward to Spec writer>
```
