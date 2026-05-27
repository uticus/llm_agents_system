# Domain Reference
# File: .cursor/memory/project/domain.md

> Maintained by: Memory writer
> Purpose: domain constraints relevant to the project that drive architectural decisions.
> Agents read this to understand the problem space before design and implementation.
> This is NOT a general project description. Focus on constraints that affect code structure.
>
> [SETUP] Fill in all sections below. Replace the placeholder content with the actual
> domain constraints for this project. See SETUP.md for instructions.

---

## Domain characteristics (implementation-relevant)

<!-- SETUP: Describe the domain properties that affect code structure.
     Focus on constraints, not features.
     Examples: scale, determinism requirements, performance budgets, concurrency, etc. -->

| Property | Value |
|---|---|
| [Property 1] | [Value] |
| [Property 2] | [Value] |

---

## Primary objective

<!-- SETUP: State what the system must achieve in domain terms. -->

[One paragraph describing what the system must do in domain terms.]

---

## Information structure

<!-- SETUP: Describe what inputs the system receives and from where. -->

### Inputs
- [Input type 1]: [description]
- [Input type 2]: [description]

### Outputs
- [Output type 1]: [description]
- [Output type 2]: [description]

---

## Scale and performance constraints

<!-- SETUP: Fill in the actual scale numbers and performance requirements. -->

- [Dimension 1]: [constraint]
- [Dimension 2]: [constraint]

---

## Determinism requirements

<!-- SETUP: State whether the system must be deterministic and under what conditions.
     Remove this section if not applicable. -->

[Determinism requirement — e.g. "Same input → identical output for reproducibility."]

---

## Domain-specific edge cases

<!-- SETUP: List edge cases that must be handled, derived from domain knowledge.
     These feed directly into test design scenarios. -->

- [Edge case 1]: [description and handling rule]
- [Edge case 2]: [description and handling rule]
