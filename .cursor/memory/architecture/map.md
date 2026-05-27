# Architecture Map
# File: .cursor/memory/architecture/map.md
# Maintained by: Memory writer + Architect

> Used by: Architect, Planner, Critic, Reviewer, Implementer
> Purpose: module boundaries, layer rules, invariants, and dependency graph.
> Update when: architectural decisions change the structure.
>
> [SETUP] Fill in all sections below. This file is created by the Architect
> during the first design task. See SETUP.md for instructions.
> Until populated, agents note: "Architecture map not yet established."

---

## System identity

<!-- SETUP: One paragraph describing what the system is and what it does. -->

[System identity — to be filled by Architect during first design task.]

---

## Module list

<!-- SETUP: List all modules with their responsibilities. -->

| Module | Location | Responsibility |
|---|---|---|
| [Module 1] | [path] | [what it owns and does] |
| [Module 2] | [path] | [what it owns and does] |

---

## Layer structure

<!-- SETUP: Define the architectural layers and which modules belong to each. -->

```
[Layer 1 name]:  [modules in this layer]
[Layer 2 name]:  [modules in this layer]
[Layer 3 name]:  [modules in this layer]
Public API:      [public interface modules]
Bindings:        [binding layer] (if applicable)
```

---

## Layer dependency rules

<!-- SETUP: Define which layers may depend on which. -->

Allowed:
- [Layer A] → [Layer B]
- [Layer B] → [Layer C]

Forbidden:
- [Layer C] → [Layer A] (backflow)
- Any layer → modifying public API without ABI assessment
- Bindings → anything beyond public API surface

---

## Invariants

<!-- SETUP: List invariants that must hold at all times. -->

- [Invariant 1]
- [Invariant 2]

---

## Hot paths

<!-- SETUP: List performance-critical entry points and their call chains. -->

- [HotPath1]: [description of the call chain]
- [HotPath2]: [description of the call chain]

---

## Decision paths (determinism-sensitive)

<!-- SETUP: List entry points whose output must be deterministic.
     Remove this section if not applicable. -->

- [DecisionPath1]: [what it produces]
- [DecisionPath2]: [what it produces]
