# Skill: C++ Implementation
# File: .cursor/skills/impl-cpp.md
# Used by: Implementer: C++

> Algorithm for implementing C++ changes following §spec.
> Goal: produce correct, reviewable, deterministic code step by step.
>
> [SETUP] Replace the placeholder module names and paths with your project's actual structure.
> Refer to memory/project/build.md and memory/architecture/map.md for authoritative names.

---

## Core principle

Implement exactly what §spec says. Nothing more, nothing less.
If §spec is silent on something — use the existing pattern in the module.
If there is no existing pattern — flag to developer before deciding.

---

## Algorithm

### Phase 1: Before touching any existing symbol

If the step modifies an existing symbol (function, class, field, enum):
run the full dependency analysis from `skills/dep-analysis.md`.

Collect:
- All call sites (IDE Find All References + Serena cross-check)
- All files that include the affected header
- All binding references (pybind11 `.def()`, etc. if applicable)
- All export macros

Do not start coding until the complete impact is known.

### Phase 2: Write tests first

Before implementing the change — write test code for all §test-criteria scenarios
relevant to this step.

**Step 2a: Write test code**

```cpp
TEST(SuiteName, ScenarioName) {
    // Given
    <construct initial state per §test-criteria Given>

    // When
    <call function per §test-criteria When>

    // Then
    <assert observable outcome per §test-criteria Then>
}
```

Test naming: `SuiteName` = class or module under test, `ScenarioName` = observable outcome.
Example: `TEST(MovementEstimator, returns_empty_when_no_valid_moves)`

Integration tests: use exact command sequence from §test-criteria.
Do not reorder. Do not simplify.

**Step 2b: Verify test coverage**

For each written test, verify it actually checks the required functionality:

- Does the `Then` assertion map directly to a post-condition in §test-criteria?
- Would the test PASS if the implementation is wrong (false positive)?
  — If yes: the assertion is too weak — strengthen it
- Would the test FAIL if the implementation is correct (false negative)?
  — If yes: the Given/When setup is incorrect — fix it
- Does the test cover the exact scenario described — not a simpler approximation?

Cross-check: read §test-criteria scenario → read test code → confirm they match.
If in doubt: a test that always passes regardless of implementation is useless.

**Step 2c: Build and run**

Build the test target and run — confirm:
- Tests compile without errors
- Tests fail (expected — implementation not yet written)
- Failure message is meaningful — it points to the right assertion

If a test cannot compile at this point — the stub may be missing.
Check `sessions/task-NNN-env.md` for available stubs.

### Phase 3: Implement the change

Before writing the first line of implementation — verify the step against architecture:

```
For each new class or function in this step:
  [ ] Layer: does it belong to the correct layer from memory/architecture/map.md?
  [ ] Dependencies: does it introduce a new inter-module dependency?
      If yes — is this dependency in §architecture? If not — flag to Architect.
  [ ] Hot path: is this called in a performance-critical path?
      If yes — apply rules/hotpath.md strictly.
  [ ] Decision path: does this affect ordering, selection, or output?
      If yes — apply rules/determinism.md strictly.
```

If any check fails before coding — flag to developer. Do not code around it.

Follow §spec entry for the step:

**Adding a new class:**
1. Create header in the correct source directory (public or internal per §spec)
2. Add `#pragma once` — only accepted include guard form
3. Write class declaration per §spec Interface section
4. Add source file
5. Add both files to the correct build target
6. Implement method bodies per §spec Contract section
7. Build the library target — verify clean

**Modifying an existing class:**
1. Make header change first (if any)
2. Update all callers identified in Phase 1
3. Update implementation
4. Build — verify all affected targets compile
5. Fix all compilation errors before proceeding

**Adding a field:**
1. Add to header — private unless §spec says otherwise
2. Initialize in constructor per §spec
3. Add invalidation in lifecycle method per §spec
4. Build — verify no uninitialized member warnings

**Changing a public method signature:**
1. Update public header first
2. Update implementation
3. Update all callers in source and tests
4. Update examples if in scope
5. Flag for binding update if applicable
6. Build all affected targets — verify clean

### Phase 3: Hot-path compliance

After implementing any change in a hot-path function, verify:

```
<!-- SETUP: Replace with actual hot-path entry points for your project. -->

Check each hot path change:
  [ ] No new heap allocation (new, make_shared, make_unique, vector resize)
  [ ] No new std::map / std::unordered_map usage
  [ ] No new virtual dispatch in tight loops
  [ ] No new logging or I/O
  [ ] No new N×M nested loops without explicit justification
```

If a violation is unavoidable — stop and flag to Architect.
Do not add allocation to a hot path without an ADR.

### Phase 4: Determinism compliance

After implementing any change in a decision path, verify:

```
<!-- SETUP: Replace with actual decision paths for your project. -->

Check each decision path change:
  [ ] Container iteration uses stable ordering
  [ ] No std::unordered_map / std::unordered_set iterated for decisions
  [ ] No pointer values used as sort keys
  [ ] std::sort on equal elements uses stable tie-breaking key
  [ ] RNG uses project centralized RNG — not std::rand()
```

### Phase 5: Ownership compliance

For every new object or field:

```
  [ ] Owning pointer: std::unique_ptr or std::shared_ptr (no raw owning T*)
  [ ] Non-owning reference: const T& or T* with explicit "non-owning" comment
  [ ] Constructor initializes all members
  [ ] Destructor/RAII handles cleanup — no manual delete
  [ ] const-correctness: methods that don't mutate are const
```

### Phase 6: Build verification sequence

After completing each §plan step, run in order:

```bash
# From project root — always
<build command> --target <library-target>
<build command> --target <test-target>
<test runner> <relevant pattern>
```

If example is in scope:
```bash
<build command> --target <example-target>
```

Record result in `sessions/task-NNN-impl.md`.

---

## Existing code patterns to follow

Before implementing anything new in a module — read 2-3 existing examples
of the same pattern in that module. Follow the established style:
- Include order (system headers, then project headers)
- Naming conventions (member prefixes, method naming)
- Error handling style (assert vs exception vs return code)
- Comment style and density

Do not introduce a new style in isolation.
