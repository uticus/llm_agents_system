# Skill: Architecture Compliance Check
# File: .cursor/skills/arch-check.md
# Used by: Reviewer, Implementer: C++

> Algorithm for verifying that code changes respect architectural invariants.
> Goal: catch architectural violations before they enter the codebase.
>
> [SETUP] Replace the placeholder layer definitions with the actual layers from
> memory/architecture/map.md for this project. The generic structure below
> is a starting point — not the final answer.

---

## Core principle

Architectural violations are the hardest bugs to fix later.
A violation discovered in review costs an hour.
The same violation discovered in production costs a sprint.

Check architecture first — before style, before performance details.

---

## Algorithm

### Phase 1: Identify the layer

For each new or modified class/function, determine its architectural layer.
Layers are defined in `memory/architecture/map.md`.

<!-- SETUP: Replace placeholder layer names with the actual layers for this project. -->
```
<Layer A>: <list of classes/modules in this layer>
<Layer B>: <list of classes/modules in this layer>
<Layer C>: <list of classes/modules in this layer>
Public API: <include dir> — <public interface classes>
Bindings:   <bindings source file>
```

If the class does not fit any layer → flag. New layer requires architectural decision.

### Phase 2: Check layer dependencies

Verify: does the changed code introduce a dependency on another layer?

<!-- SETUP: Replace with the actual allowed and forbidden dependency directions
     from memory/architecture/map.md for this project. -->
```
Allowed dependency directions (top → bottom):
  <Layer A> → <Layer B>
  <Layer B> → <Layer C>

Forbidden:
  <Layer C> → <Layer A> (backflow)
  Any layer → modifying public API without ABI assessment
  Bindings → anything beyond public API surface
```

If a new dependency is introduced not in the above → [BLOCKING].
Reference: `memory/architecture/map.md §layer dependency rules`.

### Phase 3: Run checklist sections

For the type of change being made, run the relevant checklist sections
from `memory/architecture/checklist.md`:

<!-- SETUP: Replace with the actual checklist sections for this project. -->
| Change type | Checklist sections |
|---|---|
| New component | §scope, §boundary rules |
| Public API change | §scope, §binding boundary |
| Hot-path change | §performance |
| Any decision path | §determinism |

### Phase 4: Check specific invariants

**Boundary check:**
```
Search changed code for:
  - Logic in the binding layer that belongs in core
  - Core layer depending on a binding layer type
If found → [BLOCKING] boundary violation
```

**Backflow check:**
```
Search changed code for:
  - Lower layer modifying state owned by upper layer
  - Lower layer calling ordering/priority methods on upper layer
If found → [BLOCKING] architectural backflow
```

### Phase 5: Report findings

For each architectural violation found:
```
[BLOCKING] Architectural violation: <type>
Location: <file>:<line>
Invariant violated: <specific rule from map.md or checklist.md>
Evidence: <what the code does that violates it>
Directed to: Implementer | Architect
```

For boundary questions:
```
[QUESTION] Layer boundary unclear: <description>
Code in <file> appears to belong to <layer A> but calls into <layer B>.
Is this dependency in §architecture? If not, Architect decision needed.
```
