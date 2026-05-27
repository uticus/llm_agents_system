# Rules: Testing
# File: .cursor/rules/testing.md
# Applied by: Test designer, Tester, Implementer


> Test coverage requirements and forbidden patterns.

---

## Coverage requirements

### Minimum coverage per spec entry
- Every post-condition: at least one unit scenario
- Every invariant: at least one before/after verification
- Every error path: at least one scenario
- Every hot-path change: at least one performance scenario
- Every AI decision path change: at least one determinism scenario

### Integration test requirement
- Every task that changes AI behavior must have at least one integration scenario
- Integration scenarios must use real usage sequences from the project's integration test scripts
  or gamedata JSON files
- [CRITICAL] Do not reorder, simplify, or optimize command sequences
- New sequences not from existing scripts must be flagged and confirmed by developer

### Scenario completeness
Every scenario must have:
- Given: reproducible initial state (constructable from code)
- When: single action (or exact sequence for integration)
- Then: observable, verifiable outcome — not intent

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| Then: "works correctly" | Not verifiable — test cannot fail deterministically |
| Then: "behaves as expected" | Not verifiable |
| Integration test with reordered commands | Violates integration test rule — game state becomes incorrect |
| Performance threshold with no baseline | Arbitrary — cannot be enforced |
| Scenario that tests §plan intent instead of §spec post-condition | May pass even if spec is violated |
| Skipping error path scenarios | Error paths reach production untested |
| Determinism scenario omitted when AI decision path touched | Non-determinism is silent — hardest to find later |

---

## Test independence rule

Each unit scenario must be independent:
- Does not depend on execution order of other scenarios
- Uses its own initial state — does not share mutable state with other tests
- Cleans up after itself (or uses fixtures that do)

Integration scenarios may share game state if they form a sequence —
but the sequence must be explicitly documented as ordered.

---

## Regression rule

All existing tests must pass after implementation.
If a test fails after implementation and the test was correct:
- The implementation is wrong — fix implementation
- The test is wrong — flag to developer, do not silently update the test

No test may be deleted or weakened to make the implementation pass.

---

## Naming rule

Scenario names must describe the observable outcome, not the implementation:
- Good: "returns_empty_when_no_valid_moves"
- Bad: "test_cache_update"
- Good: "command_sequence_identical_across_runs_with_same_seed"
- Bad: "determinism_test"


