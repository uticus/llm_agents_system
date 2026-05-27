# Rules: Request Decomposition
# File: .cursor/rules/decompose.md

> Applied by: Decomposer
> Defines what makes a valid decomposition and what is forbidden.

---

## Valid task card

A task card is valid when:
- It describes exactly one independent unit of work
- It can be implemented without waiting for another card
  (or its dependency is explicitly stated)
- It has one implementer type: C++ / Python / ML
- Its title describes the outcome, not the implementation method
- Its scope fits within a single implementer session (small or medium)

## Invalid decompositions

| Pattern | Why invalid |
|---|---|
| Card touches two independent modules with no shared state or symbols | Split into two cards |
| Card mixes refactoring and new functionality | Always separate — verification becomes impossible |
| Card mixes C++ implementation and Python binding update | Separate — different implementer, skills, and rules |
| Card has implicit dependency on another card | Make dependency explicit or merge |
| Card is "large" with no documented reason | Must attempt to split or flag for developer |
| Card title describes implementation ("Refactor X") not outcome ("Improve Y performance") | Rewrite title |

---

## Dependency rules

- Dependencies must be explicit in `§decomposition`
- Dependencies must be directional — no circular dependencies
- A card may depend on at most one other card from the same request
  (deeper chains indicate the request needs redesign)
- Do not create dependencies between cards from different requests

---

## What Decomposer must not decide

- Which architectural pattern to use
- Which files to modify
- How to implement the change
- What the test scenarios are
- Whether a constraint from `§constraints` can be relaxed

These are resolved by Architect, Planner, Test designer, and the developer.
If decomposition requires an architectural decision — flag it as an open question
in the task card and let Architect resolve it.

---

## Confirmation requirement

- Never write task cards without explicit developer confirmation of the decomposition plan
- If the developer requests a change to the plan — revise and confirm again
- Acceptable confirmations: "yes", "go ahead", "looks right"
- Not acceptable: silence, "maybe", partial agreement

---

## One request — one decomposition session

Each `request-NNN.md` produces one set of task cards in one session.
Do not mix cards from different requests.
Do not add cards to an existing decomposition without starting a new analyst session.

---

## Numbering

Task card numbers are global and sequential across all requests.
Check `tasks/active/` and `tasks/archive/` for the highest existing number
before assigning new numbers.
Never reuse a number, even if a card is abandoned.
