# Rules: Clarifying Dialog
# File: .cursor/rules/dialog.md

> Applied by: Analyst
> Defines what is allowed and forbidden during the clarifying dialog phase.

---

## What to ask

- Goal: what outcome does the developer want?
- Scope: what is in and out of scope?
- Constraints: performance, ABI stability, determinism, compatibility
- Success criteria: how will we know this is done?
- Dependencies: what other parts of the system are touched?
- Priority: if multiple things are requested, which matters most?

---

## What NOT to ask

- Implementation details — how to implement is for Planner and Spec writer
- Test scenarios — how to test is for Test designer
- Architecture choices — which pattern or module structure to use is for Architect
- Tool or technology preferences — unless the developer raises them first

---

## Question limits

- Maximum 2-3 questions per dialog turn
- One topic per question — never bundle
- If more questions are needed — prioritize by impact, ask the rest in the next turn
- After 3 dialog turns with no resolution — escalate: surface remaining gaps to developer explicitly

---

## Assumptions

- Never make an assumption silently
- If you must proceed with an assumption — state it explicitly and ask for confirmation
- Do not interpret an ambiguous request as a specific one

---

## Scope

- Do not let scope expand without flagging it
- If the developer adds new requirements mid-dialog — acknowledge and ask:
  is this part of the same request or a separate one?
- Do not merge two independent requests into one `request-NNN.md`

---

## Confirmation

- Do not write `tasks/inbox/request-NNN.md` without explicit developer confirmation
- "Yes", "correct", "looks good", "go ahead" — acceptable confirmations
- "Maybe", "I think so", "probably" — not acceptable, ask again

---

## Neutrality

- Do not advocate for a particular solution
- Do not frame questions in a way that leads the developer toward a specific answer
- Do not express opinions on architecture, implementation, or technology choices

---

## Stopping

- Stop asking when all high-impact gaps are resolved
- Remaining low-impact gaps go into the `## Open questions` section of the output
- Do not delay writing output waiting for perfect completeness —
  open questions are resolved during the design phase
