# loop-impl.md
# Implementation Loop — Implementer + Reviewer + Tester

> Rules for Phase 5 of the pipeline.
> Read this file if you are an Implementer, Reviewer, or Tester.
> Authoritative flow is in `pipeline.md`. This file defines the loop mechanics.
>
> Key properties of this loop:
> - Escalation rule: if spec is contradictory or arch decision is wrong — stop, do not improvise, escalate to CP2.
> - Tester runs the full suite every iteration, not just changed tests.
> - Reviewer re-reviews the full diff since last clean state, not just the fix.
> - Unified session log with iteration markers — developer sees what is happening at any time.

---

## Purpose

The implementation loop produces verified, reviewed, test-passing code.
It is iterative: Implementer fixes issues raised by Reviewer and Tester until both agree.
No output is marked ready until the stop condition is met and the developer approves at CP5.

---

## Participants

| Agent | Role in loop |
|---|---|
| Implementer (C++ / Python / ML / ...) | Writes code following `§spec`. Fixes issues from Reviewer and Tester. |
| Reviewer | Reviews code against spec and architecture. Returns [BLOCKING] issues. |
| Tester | Runs build and test suite against `§test-criteria`. Reports failures. |

---

## Loop flow

```
Implementer writes code per §spec
        |
        v
Reviewer reviews code
        |
   [BLOCKING issues?]
        |
   yes  |  no
   _____|_____
  |           |
  v           v
Reviewer   Tester runs tests
feedback        |
  |        [all criteria PASS?]
  |             |
  |        yes  |  no
  |        _____|_____
  |       |           |
  v       v           v
Impl   stop        Tester
fixes  condition   feedback
code   met              |
  |___________________|
  (loop back to Implementer)
```

---

## Iteration rules

- Each iteration is appended to `tasks/sessions/task-NNN-impl.md` with a clear marker.
- Implementer must address every [BLOCKING] issue from Reviewer before requesting Tester run.
- Tester runs the full test suite every iteration — not just the changed tests.
- Reviewer re-reviews the full diff since the last clean state — not just the fix.
- Maximum iterations: not fixed. Loop continues until stop condition is met.
  If no progress after 3 iterations — surface the deadlock to the developer.
- [WARNING] issues do not block loop completion. They are recorded in the review report.

---

## Feedback classification

Reviewer and Tester classify every issue:

| Severity | Meaning | Effect |
|---|---|---|
| [BLOCKING] | Must be fixed before loop can complete | Loop continues |
| [WARNING] | Should be addressed but does not block | Recorded in review report |
| [QUESTION] | Needs clarification from developer or Architect | Pause loop, ask |

If a [QUESTION] cannot be answered within the loop — stop and surface to the developer.
If the answer requires an architectural change — escalate to CP2, do not improvise.

---

## Stop condition

The loop stops when ALL of the following are true:

- Reviewer confirms: zero [BLOCKING] issues. Code matches spec and architecture.
- Tester confirms: all criteria in `task-NNN.md §test-criteria` pass.

When stop condition is met:
1. Write review report to `tasks/decisions/task-NNN-review.md` marked READY
2. Update `task-NNN.md Status:` to `implemented-awaiting-CP5` (Tester responsibility)
3. Call Memory writer if implementation revealed new architectural facts
4. Stop and surface output for developer review — CP5

---

## Status transitions in this loop

Each agent updates `Status:` in the task card at each transition.
Full vocabulary is in `pipeline.md §6`.

| Transition | Who sets it | Value |
|---|---|---|
| Implementer begins (or resumes) implementation | Implementer | `impl-in-progress` |
| Implementation complete, passed to Reviewer | Implementer | `implemented` |
| Reviewer begins evaluation (each iteration) | Reviewer | `reviewing` |
| Reviewer REQUEST CHANGES — returned to Implementer | Reviewer | `impl` |
| Reviewer AGREE — passed to Tester | Reviewer | `reviewed` |
| Tester begins running suite | Tester | `testing` |
| Tester failures — returned to Implementer | Tester | `impl` |
| Both Reviewer + Tester AGREE | Tester | `implemented-awaiting-CP5` |
| Escalation stops the loop | whichever agent detects it | `impl-blocked` |

---

## What Reviewer must check

Reviewer is required to evaluate every iteration against all of the following:

- Spec compliance: does the implementation match `task-NNN.md §spec` exactly?
- Architecture compliance: does code respect invariants in `.cursor/memory/architecture/map.md`?
- Public API: are there unintended changes to public headers or exported symbols?
- ABI stability: if public API changed — is ABI impact analyzed and acceptable?
- Ownership and lifetime: are RAII, smart pointers, and const-correctness applied correctly?
- Hot-path: are there allocations, virtual dispatch, or heavy STL in AI tick loops?
- Bindings: if Python bindings changed — are types, enums, and exceptions consistent?
- Test coverage: does the implementation enable verification by `§test-criteria`?

Reviewer must not approve code that has any [BLOCKING] issue in the above categories.

---

## What Tester must verify

Tester runs and reports on all of the following:

- Build succeeds with no errors and no new warnings
- All existing tests pass (regression check)
- All new tests defined in `§test-criteria` pass
- Integration tests replicate gameplay scripts exactly — no reordering of commands
- If determinism is required: results are identical across multiple runs with same seed

Tester reports each failure with: test name, failure reason, and relevant output.

---

## Escalation to CP2

If during implementation the Implementer or Reviewer discovers that:
- The spec is insufficient or contradictory
- The architectural decisions in `§architecture` are incorrect or incomplete
- A correct implementation is not possible within the current plan

— do not improvise. Stop the loop, document the finding in the session file,
and surface it to the developer. The developer decides whether to escalate to CP2
(revise the plan) or provide clarification to continue.

---

## Session file format for this loop

```markdown
# Session: task-NNN — implementation loop

## Iteration 1

### [Implementer: C++] progress
<what was implemented, key decisions made during coding>

### [Reviewer] review
[BLOCKING] file.cpp:42 — <issue and suggested fix>
[WARNING] file.cpp:88 — <issue>
Overall: REQUEST CHANGES

### [Tester] results
Build: OK
Tests: 3 FAIL
  - test_name_1: <failure reason>
  - test_name_2: <failure reason>
  - test_name_3: <failure reason>

## Iteration 2

### [Implementer: C++] fixes
<what was changed and why>

### [Reviewer] review
[BLOCKING] 0 remaining
[WARNING] file.cpp:88 — carried forward
Overall: APPROVE (with warnings)

### [Tester] results
Build: OK
Tests: all PASS

## Agreed — iteration N

### Stop condition confirmed
- Reviewer: zero [BLOCKING] issues
- Tester: all criteria PASS

### Remaining [WARNING] items
<list — recorded in decisions/task-NNN-review.md>

### Ready for CP5
```
