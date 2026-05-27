# Rules: Build System
# File: .cursor/rules/build.md
# Applied by: Environment, Implementer, Tester

> Build system conventions and rules for this project.
> For build facts (preset names, target names, paths): see memory/project/build.md
>
> [SETUP] Populate memory/project/build.md with actual preset names and targets.
> Update the tables below with project-specific targets if needed.

---

## Project root rule

All build commands must be run from the project root.
Never use `cd` into a subdirectory before running build tools.
Relative paths in build configurations are resolved from the project root.
Running from a subdirectory causes silent path resolution failures.

---

## Build tool rules

<!-- SETUP: Replace with actual build tool (cmake, npm, cargo, make, etc.). -->

- Use presets or configurations defined in the project — do not invent ad-hoc configurations.
- Build specific targets — do not build everything when only one target changed.
- Never modify build configuration files to work around a build issue without developer approval.
- Never modify files fetched by a dependency manager — see `rules/no-deps-touch.md`.

### Standard build sequence

```bash
# From project root — always:
<configure command>
<build command> --target <target>
<test command>
```

---

## Target naming

Verify actual target names in build configuration before using them.
Do not guess. See `memory/project/build.md` for authoritative names.

---

## Impact matrix

When changing a component — which targets must be rebuilt and verified:

<!-- SETUP: Fill in the project-specific impact matrix. -->
<!-- Example structure: -->

| Change | core library | tests | bindings | examples |
|---|---|---|---|---|
| Internal impl | build | build + run | — | build |
| Public header | build | build + run | build + verify | build + run |
| Bindings layer | — | — | build + verify | build + run |

---

## Stub rules

Stubs created by Environment agent must:
- Compile without errors or warnings
- Contain no business logic — marked with `// STUB: task-NNN step N`
- Be added to the correct build target
- Be listed in `sessions/task-NNN-env.md`
- Not be merged — Implementer replaces them during implementation

---

## Verification requirement

Always verify — not assume:
- Build runs without error after stubs are created
- Test runner finds and executes tests
- All bindings can be imported (if applicable)

Document actual command output in `sessions/task-NNN-env.md`.
"Should work" is not a verification result.
