# Skill: Code Review
# File: .cursor/skills/code-review.md
# Used by: Reviewer

> Algorithm for systematically reviewing implementation against §spec and architecture.
> Goal: find every blocking issue before code reaches Tester or production.

---

## Core principle

Review against §spec and rules — not against personal preference.
Every [BLOCKING] issue must reference a specific §spec entry, rule file, or architecture invariant.
"I would have done it differently" is not a blocking issue.

---

## Algorithm

### Phase 1: Orient

Before reading any code:
1. Read §spec completely — know what the implementation must do
2. Read §architecture — know the constraints
3. Read `sessions/task-NNN-impl.md` — understand what changed in this iteration
   and what was already discussed in previous iterations
4. Read Reviewer [WARNING] items from previous iterations — check if addressed

### Phase 2: Review each changed file

For each changed file, answer all six questions:

**Q1: Spec compliance**
```
For each changed symbol:
  - Does the signature match §spec Interface exactly?
  - Does the behavior satisfy every §spec Contract post-condition?
  - Does error handling match §spec Error handling?
  - Are integration points correct (called from / calls into)?
```

**Q2: Architecture compliance**
```
Check against memory/architecture/map.md:
  - Which layer does this code belong to?
  - Does it introduce a dependency not in §architecture?
  - Any layer boundary violation (lower layer calling upper layer)?
  - Any cross-concern action not in §architecture?
Check against memory/architecture/checklist.md:
  - Run through relevant sections for this type of change
```

**Q3: Hot-path compliance**
```
Is this code in a hot path? (See memory/architecture/map.md for the list.)
If yes:
  - Any heap allocation? (new, make_shared, vector resize)
  - Any virtual dispatch in loops?
  - Any logging or I/O?
  - Any unexpected N×M complexity?
```

**Q4: Determinism compliance**
```
Is this code in a decision path (see memory/architecture/map.md)?
If yes:
  - Any std::unordered_map / std::unordered_set iteration?
  - Any pointer values as sort keys?
  - std::sort without stable tie-breaking on equal elements?
  - Any non-centralized RNG?
```

**Q5: Ownership and safety**
```
  - Any raw owning T*?
  - Smart pointer choices match §spec Ownership?
  - Constructor initializes all members?
  - Any dangling reference risk?
  - Const-correctness maintained?
```

**Q6: Test quality**
```
For each test file changed:
  - Tests written before implementation (check impl log order)?
  - Each assertion maps to a §test-criteria post-condition?
  - Would test pass if implementation returns wrong value? (false positive check)
  - Are integration tests using exact command sequences from §test-criteria?
  - No tests weakened or deleted?
```

### Phase 3: Classify and direct

For each issue found:
- Is the code incorrect, unsafe, or non-compliant? → [BLOCKING]
- Is the code functional but suboptimal? → [WARNING]
- Cannot assess without more info? → [QUESTION] — stops loop

Direct each issue:
- Implementation problem → Implementer
- Architectural decision needed → Architect + developer
- §spec ambiguity → Spec writer + developer

### Phase 4: Deadlock check

Count how many iterations the same [BLOCKING] issue has been raised.
If 3 times without resolution → surface deadlock to developer.

### Phase 5: Decide

Zero [BLOCKING]: write AGREE.
Any [BLOCKING]: write REQUEST CHANGES.
Any [QUESTION]: stop loop, surface to developer.

---

## False positive test detection

A test is a false positive if it passes regardless of implementation correctness.
Check:
- Does the assertion compare a specific value (not just `!= nullptr`)?
- Does the Given state actually set up the scenario described in §test-criteria?
- Would the test fail if the function returned a default-constructed object?
- For integration tests: does the expected output match what the game rules require?

If uncertain: mentally trace through what happens if the implementation
returns the wrong value. Does the test catch it? If not → [BLOCKING].

---

## Quality check before writing verdict

Before writing AGREE or REQUEST CHANGES:
- [ ] All six categories checked for all changed files
- [ ] No issue from previous iterations re-raised if validly resolved
- [ ] Every [BLOCKING] references a specific rule, §spec entry, or invariant
- [ ] [QUESTION] items surfaced if loop must pause
- [ ] Deadlock condition checked
