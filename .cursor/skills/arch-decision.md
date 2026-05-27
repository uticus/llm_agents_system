# Skill: Architectural Decision Making
# File: .cursor/skills/arch-decision.md
# Used by: Architect

> Algorithm for making, evaluating, and recording architectural decisions.
> Goal: produce decisions that are traceable, justified, and implementable.

---

## Core principle

An architectural decision is not a preference — it is a constraint on all future work.
Every decision must be justified, have documented alternatives, and state its consequences.
A decision without alternatives considered is an assumption, not a decision.

---

## Algorithm

### Phase 1: Frame the problem

Before considering solutions, state the problem precisely:

```
Problem: <what architectural challenge does this task create?>
Forces: <what constraints, qualities, or trade-offs are in tension?>
Context: <what existing decisions and invariants apply?>
```

A problem poorly framed leads to a solution that solves the wrong thing.
Do not move to Phase 2 until the problem is clearly stated.

### Phase 2: Identify alternatives

Generate at least 2 alternatives. For each:
- Name it
- Describe it in 1-2 sentences
- Identify its primary advantage
- Identify its primary disadvantage
- Check it against existing ADRs and architecture invariants

Do not evaluate yet — just enumerate.

Common alternative axes for this project:
- New abstraction vs extending existing one
- Compile-time vs runtime decision
- Owning vs non-owning (shared_ptr vs raw ref vs unique_ptr)
- Phase-specific vs shared mechanism
- Inline vs separate module

### Phase 3: Evaluate against criteria

Score each alternative against the project's quality criteria:

| Criterion | Question |
|---|---|
| Performance | Does this introduce allocations or virtual dispatch in the hot path? |
| ABI stability | Does this change the public interface? Is it additive or breaking? |
| Determinism | Does this preserve deterministic AI behavior? |
| Testability | Can the resulting code be tested against §test-criteria? |
| Maintainability | Does this fit the existing module structure or create new coupling? |
| Implementability | Can the assigned Implementer execute this within the task scope? |

### Phase 4: Choose and justify

State the chosen alternative and:
- Why it scores best against the criteria
- What it trades off (what gets worse)
- What constraints it imposes on Implementer

The justification must be specific. "It's simpler" is not a justification.
"It avoids a virtual dispatch in the AI tick loop (see rules/hotpath.md)" is a justification.

### Phase 5: Determine if ADR is required

ADR required if the decision:
- Changes a public interface or ABI
- Introduces a pattern not previously used in the project
- Explicitly trades off one quality for another
- Overrides or supersedes an existing ADR

If ADR required — prepare the ADR entry content and flag for Memory writer.

### Phase 6: Write §architecture

Use the format defined in `architect.md`.
Be explicit. Implementer must be able to work from §architecture alone
without asking clarifying questions.

---

## Evaluating Critic feedback

When Critic returns an architectural issue:

1. Read the issue precisely — what specific concern is raised?
2. Check: is this concern valid given the problem framing?
3. Check: does this concern change the trade-off evaluation?
4. If valid — revise the decision, document what changed and why
5. If not valid — explain specifically why the current decision stands

Do not revise silently. Every revision must be documented in the session log.
Do not dismiss Critic feedback without explanation.

---

## Quality checks

Before finalizing a decision:

- [ ] Problem is framed, not assumed
- [ ] At least 2 alternatives documented with rejection rationale
- [ ] Decision justified against specific project criteria
- [ ] ABI impact assessed (additive / breaking / none)
- [ ] Hot-path impact assessed (allocations / virtual dispatch)
- [ ] Determinism impact assessed
- [ ] Constraints for Implementer are explicit
- [ ] ADR requirement determined
