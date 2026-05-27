# Skill: Plan Critique
# File: .cursor/skills/critique.md
# Used by: Critic

> Algorithm for systematically attacking a plan to find every reason it could fail.
> Goal: surface all blocking issues before implementation begins.

---

## Core principle

The Critic's job is not to find a reason to reject — it is to find every reason the plan
could fail if implemented as written. Thoroughness matters more than speed.
A plan approved with a hidden gap will fail at implementation and cost more to fix.

---

## Algorithm

### Phase 1: Orient

Before evaluating anything, answer:
- What does §request say the outcome must be?
- What does §architecture say is allowed and forbidden?
- What did previous Critic iterations flag, and how was it resolved?

Do not evaluate the new iteration until you understand the context of prior rounds.

### Phase 2: Evaluate each step in isolation

For each step, ask:
1. Is the file list complete? (Check all consumers of changed symbols)
2. Is the change specific enough? (Would Implementer know exactly what to write?)
3. Does this step violate any §architecture constraint?
4. Does this step violate any `memory/architecture/checklist.md` rule?
5. Is the risk assessment correct? (Check ABI, Perf, Det, Bindings independently)
6. Is the dependency correctly stated? (Will the codebase compile after this step?)

### Phase 3: Evaluate the plan as a whole

After evaluating each step:
1. Does the complete sequence of steps implement §request §goal?
2. Are there missing steps for: test updates, binding updates, example updates?
3. Does any step mix refactoring with new functionality?
4. Does any step make a decision not in §architecture?
5. Does the plan cover all affected symbols (not just the ones explicitly mentioned)?

### Phase 4: Classify each issue

For each issue found:
- Is the plan non-functional without fixing it? → [BLOCKING]
- Is the plan functional but risky or incomplete? → [WARNING]
- Can Critic not assess without more information? → [QUESTION]

Do not use [WARNING] to avoid conflict on issues that are actually [BLOCKING].

### Phase 5: Check deadlock condition

Count how many times each [BLOCKING] issue has been raised across all iterations.
If the same issue has been raised 3 times without resolution → surface deadlock to developer.

### Phase 6: Decide and write feedback

If zero [BLOCKING]: write AGREE with [WARNING] list.
If any [BLOCKING]: write REQUEST CHANGES with full issue table.

Always append to `sessions/task-NNN-plan.md` with iteration marker.
