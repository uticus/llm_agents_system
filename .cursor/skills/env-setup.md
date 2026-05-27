# Skill: Environment Setup
# File: .cursor/skills/env-setup.md
# Used by: Environment agent

> Algorithm for preparing a verified build environment for Implementer.
> Goal: Implementer opens the project and starts coding without friction.
>
> [SETUP] Replace placeholder target names with actual build targets from memory/project/build.md.

---

## Core principle

The environment is ready when Implementer can:
1. Build the affected targets without errors
2. Run the test scenarios from §test-criteria (even if they fail — they must run)
3. Find every stub and know exactly when to replace it

An environment that "should work" is not ready. Only a verified environment is ready.

---

## Algorithm

### Phase 1: Determine build scope

Read §spec and §decomposition. Answer:

```
Implementer type: cpp | python | ml
Affected library target:  <from memory/project/build.md>
Affected test target:     <from memory/project/build.md>
Affected binding target:  <if Python task>
Affected example target:  <if examples in §plan>
Build preset / config:    <from memory/project/build.md>
```

If `memory/project/build.md` does not exist:
- Read the project's build configuration (CMakeLists.txt, package.json, Cargo.toml, etc.)
- Read the test configuration
- Note the build layout for Memory writer to persist

### Phase 2: Verify build baseline

Run from project root — never from a subdirectory:

```bash
# Configure (if needed)
<configure command> --preset <preset>

# Build affected targets only
<build command> --preset <preset> --target <target1> <target2>
```

Record: exit code, any errors or warnings.

If baseline fails:
- Classify: pre-existing (unrelated to this task) or task-related
- Pre-existing → document, do not fix, surface to developer
- Task-related → this should not happen before implementation; surface to developer

### Phase 3: Identify stubs needed

For each new symbol in §spec, ask:
"If Implementer implements step 1 of §plan, will the build succeed
without this symbol existing?"

If no → stub needed.
If yes → skip, Implementer creates it naturally.

Common cases requiring stubs:
- New header included by existing source files
- New class inherited from by existing code
- New enum value used in existing switch statements
- New method declared in an existing header (pure virtual override)

### Phase 4: Create stubs

For each stub — after creating, add to the correct build target.

Then rebuild to verify it compiles.

**Header stub:**
```cpp
// <filename>.h
// STUB: to be implemented in task-NNN step N
#pragma once

class StubClass {
public:
    // TODO: implement per §spec step N
};
```

**Source stub:**
```cpp
// <filename>.cpp
// STUB: to be implemented in task-NNN step N
#include "<filename>.h"

// Methods will be implemented per §spec step N
```

**Enum stub:**
```cpp
// Add to existing enum — STUB
NewValue, // TODO: task-NNN step N
```

After creating each stub — rebuild to verify it compiles.
If it does not compile → fix the stub until it does.
Never leave a non-compiling stub.

### Phase 5: Verify test infrastructure

For each scenario type in §test-criteria:

**Unit scenarios:**
```bash
<test runner> --preset <preset> --tests-regex <pattern>
```
Verify: test runner finds and executes tests (even if they fail — that is expected).

**Integration scenarios:**
- Verify the state loader can load the relevant scenario
- Verify the real usage scripts can be referenced

**Performance scenarios:**
- Verify address sanitizer or allocator hook is available
- Or: confirm Reviewer inspection method is sufficient

**Determinism scenarios:**
- Verify RNG seeding is accessible in test context
- Verify test can run the entry point multiple times with same state

**Python scenarios (if applicable):**
```bash
python -c "import <module_name>; print('ok')"
```
Verify: module can be imported. Run one smoke test if available.

### Phase 6: Write environment document

Write `sessions/task-NNN-env.md` using the format in `environment.md`.
Every claim in the document must be verified — not assumed.

---

## Build troubleshooting

| Symptom | First action |
|---|---|
| Configure fails | Check preset/config exists in build configuration |
| Missing dependency | Check dependency manager (FetchContent, npm, etc.) — do not modify |
| Linker error on stub | Stub source file may be missing from build target |
| Python import fails | Check that the module was built for the correct Python version |
| Test not found by runner | Check test name pattern, verify build config adds test |

If any issue cannot be resolved without modifying external deps → escalate to developer.
