# Rules: External Dependencies — Read Only
# File: .cursor/rules/no-deps-touch.md
# Applied by: Architect, Environment, Impl: C++, Impl: Python, Impl: ML, Reviewer

> Immutable rule. Cannot be overridden by any agent or any decision.
> Severity: [BLOCKING] — any violation stops the loop immediately.

---

## Rule

External fetched dependencies are read-only.
No agent may propose, suggest, or make any change to fetched dependency files.

This applies to:
- All files fetched via CMake FetchContent or equivalent mechanisms
- All files under build output directories containing fetched sources
- All headers, sources, CMake files, and any other content of external packages

To identify which directories contain fetched dependencies —
read `CMakeLists.txt` and `.cursor/memory/project/build.md` (if exists).

---

## What is allowed

- Reading dependency headers to understand interfaces
- Referencing dependency types, functions, and constants in project code
- Citing dependency documentation in §architecture or design decisions

## What is forbidden

| Action | Severity |
|---|---|
| Modifying any file in a fetched dependency directory | BLOCKING |
| Proposing a change to a fetched dependency file | BLOCKING |
| Copying and modifying dependency source into the project | BLOCKING |
| Patching dependency behavior via file replacement | BLOCKING |
| Suggesting "just edit this in the dependency" as a solution | BLOCKING |

---

## When a dependency limitation blocks progress

If the external dependency does not support a required capability:

1. Document the limitation in `§architecture` or `§open-questions`
2. Propose one of the following alternatives:
   - Wrapper or adapter in project code that works around the limitation
   - Alternative approach that does not require the missing capability
   - Request to developer to evaluate replacing or forking the dependency
3. Surface to developer — do not attempt to modify the dependency

---

## Escalation

If an agent determines that the only solution requires modifying a dependency:
- Stop immediately
- Do not propose the modification
- Surface to developer: "This task appears to require modifying [dependency].
  This violates a non-negotiable rule. Developer decision required."
- Wait for developer guidance before proceeding
