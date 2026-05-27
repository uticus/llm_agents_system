# Rules: Architecture
# File: .cursor/rules/arch.md
# Applied by: Architect, Critic, Reviewer

> Architectural invariants and forbidden patterns for this project.
> These rules apply to all architectural decisions and all code review.
> Violations are [BLOCKING] — they cannot be approved or merged.
> For the project-specific instantiation of these rules (module list, layer map, dependency graph): see `memory/architecture/map.md`.
> For per-component registry: see `memory/architecture/inventory.md`.
>
> [SETUP] Replace the placeholder rules below with the actual invariants for your project.
> Keep the structure. Delete the placeholders when real rules are populated.

---

## Immutable rules

These rules cannot be overridden by any agent or any decision:

1. External fetched dependencies are read-only. Never propose or make changes to them.
2. Public API defines the stable interface. Breaking changes require explicit developer approval and a superseding ADR.
3. Performance-critical paths must not allocate or perform expensive operations inside tight loops.
4. Behavior must be deterministic where required by the domain (see `memory/project/domain.md`).
5. Ownership and lifecycle must be explicit. No hidden lifetime coupling.

---

## Module boundary rules

- A module must not depend on another module it did not previously depend on
  without an explicit architectural decision and ADR.
- Circular dependencies between modules are forbidden.
- Internal implementation types must not leak into public headers.
- Binding / adapter layers (e.g. Python bindings, REST adapters) must not contain business logic.

---

## Interface rules

- New public symbols must follow the existing naming convention of the module.
- Every new public function must have documentation (e.g. `/// @brief` or docstring).
- Public enums must not have values removed or reordered (API stability).
- Public structs must not have fields reordered or removed (API stability).

---

## Hot-path rules

<!-- SETUP: Fill in the actual hot-path entry points for your project. -->
<!-- Delete this comment block when populated. -->

Performance-critical paths must not contain:

| Pattern | Severity | Alternative |
|---|---|---|
| Heap allocation in tight loop | BLOCKING | Pre-allocated pools, stack allocation |
| Heavy STL containers inside loop | BLOCKING | Flat sorted arrays, pre-built lookup tables |
| String construction in loop | BLOCKING | String views, pre-computed values |
| Virtual dispatch in tight inner loops | BLOCKING | Templates, policy-based design |
| Heavy logging in loop | BLOCKING | Conditional compile-time logging only |

---

## Determinism rules

<!-- SETUP: Keep this section if determinism is relevant; remove if not. -->

- All random number generation must use a seeded, deterministic RNG.
- No use of hash-map iteration in paths that affect output (iteration order is not guaranteed).
- No use of pointer values as sort keys or hash inputs in decision paths.
- No timing-dependent behavior in decision logic.

---

## Forbidden patterns (any code, any path)

- Raw owning pointers (`T*` where T is owned)
- `const_cast` without documented justification
- `reinterpret_cast` in public API
- Undefined behavior (signed overflow, out-of-bounds access, etc.)
- Platform-specific code without `#ifdef` guards and documented justification
- Magic numbers — use named constants

---

## Severity levels for checklist

| Severity | Meaning | Effect on loop |
|---|---|---|
| [BLOCKING] | Violates an immutable rule or invariant | Loop cannot complete |
| [WARNING] | Deviates from convention, does not violate invariant | Recorded, loop may complete |
| [QUESTION] | Needs clarification before assessment | Loop pauses |
