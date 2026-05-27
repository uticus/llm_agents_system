# Skill: Test Design
# File: .cursor/skills/test-design.md
# Used by: Test designer

> Algorithm for defining test scenarios and acceptance criteria
> that fully verify implementation against spec and domain requirements.
> Goal: every scenario is specific, reproducible, and maps to a verifiable outcome.
>
> [SETUP] Update Phase 4 (domain scenarios) with the actual domain facts from
> memory/project/domain.md for your project.

---

## Core principle

A test scenario is not a description of what the code does.
It is a specification of what must be true — observable and verifiable —
given a precise initial state and a precise action.

"Test that the cache works" is not a scenario.
"Given an empty cache, when GetCost() is called twice with the same input,
then the second call returns the same value without recomputing" is a scenario.

---

## Algorithm

### Phase 1: Build coverage map

For each §spec entry, list all testable obligations:

```
Step N: <plan step title>
  Post-conditions: [list each — one scenario each minimum]
  Invariants: [list each — verify before and after]
  Error paths: [list each — one scenario each]
  Constraints: [performance? determinism? — one scenario each if yes]
```

This map is the minimum coverage requirement.
Every item must have at least one scenario before §test-criteria is complete.

### Phase 2: Classify scenario types

| Type | When to use |
|---|---|
| Unit | Verifying a single function or class in isolation |
| Integration | Verifying a sequence of actions producing an observable outcome |
| Performance | Verifying hot-path constraints (allocation, timing) |
| Determinism | Verifying identical output given identical input and seed |

Assign a type to every scenario before writing it.

### Phase 3: Write precise Given/When/Then

**Given** — initial state:
- Be precise: "Manager with 3 active plans, seed 42"
- Not: "a typical state"
- Must be reproducible from code: "constructed via TestFixture::CreateState(3, 42)"

**When** — action:
- One action per scenario (exception: integration sequences)
- Specify exact function call with parameter values
- For integration: exact command sequence in order — never reorder

**Then** — verifiable outcome:
- Observable state: function return value, object field value, output sequence
- Never: "works correctly", "behaves as expected"
- For integration: exact expected output in order

### Phase 4: Domain scenario identification

Use `memory/project/domain.md` to identify domain-specific edge cases.

<!-- SETUP: Replace this section with actual domain scenarios for your project.
     Read memory/project/domain.md after setup and fill in the relevant scenarios. -->

**Scale scenarios:**
- Small: minimum viable input (1 element, empty container)
- Typical: representative scale for normal operation
- Large: maximum expected scale (if bounded by domain)

**Boundary scenarios:**
- Zero / empty inputs
- Single-element inputs
- Maximum-size inputs
- Inputs at domain boundary values

**Error scenarios:**
- Null or uninitialized inputs
- Out-of-range values
- Concurrent mutation (if relevant)

### Phase 5: Define metrics

**Performance scenarios:**
- "Does not allocate on the heap during execution" (verify with sanitizer or allocator hook)
- "Completes within N ms for M elements" (if cycle budget applies)
- "Does not introduce N×M loop" (verify by inspection in Reviewer)

**Determinism scenarios:**
- "Given same state and seed S, produces identical output sequence across 3 runs"
- "Stable under different container iteration orders" (verify with randomized iteration in debug)

### Phase 6: Check spec gaps

While defining test criteria, if a post-condition in §spec is untestable:
- Document the gap: "Post-condition X in step N cannot be tested because [reason]"
- Return to Spec writer with specific feedback
- Do not proceed to writing §test-criteria until gap is resolved

---

## Scenario format

```
Scenario N: <short descriptive name>
Type: unit | integration | performance | determinism
Given: <initial state — precise and reproducible>
When:  <action performed — function called, command issued>
Then:
  - <observable outcome 1>
  - <observable outcome 2>
Metric: <if performance or determinism — specific threshold or rule>
```

---

## Common scenario patterns

**Null input:**
```
Scenario N: <function> handles null input
Type: unit — error handling
Given: null passed to <function>()
When:  <function>(nullptr) called
Then:  assert fires in debug; behavior defined per §spec
```

**Cache:**
```
Scenario N: cache returns same value without recomputing
Type: unit
Given: freshly constructed <ClassName>
When:  GetValue() called twice with identical inputs
Then:  second call returns identical result
       (optionally: computation counter does not increment)
```

**Determinism:**
```
Scenario N: output is deterministic
Type: determinism
Given: initial state S, seed 42
When:  <entry point> called 3 times with identical inputs
Then:  output sequence is byte-identical across all 3 runs
```

**Integration:**
```
Scenario N: <description of integration outcome>
Type: integration
Given: <initial state from real usage script>
When:  <exact command sequence — do not reorder>
Then:
  - <expected output step 1>
  - <expected output step 2>
```
