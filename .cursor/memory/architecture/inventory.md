# Architecture Inventory
# File: .cursor/memory/architecture/inventory.md
# Maintained by: Memory writer + Analyst: Code

> Used by: Architect, Planner, Implementer, Environment
> Purpose: structural reference — all modules, files, and key classes.
> Update when: new files added, modules renamed, major structural changes.
>
> [SETUP] This file is populated by the Analyst: Code during the first
> architecture analysis task. See SETUP.md for instructions.
> Until populated: "Inventory not yet established — read source directly."

---

## Module inventory

<!-- SETUP: Fill in the actual inventory for each module.
     One section per module. -->

### [Module 1]

Location: [path]
Responsibility: [brief description]

Key files:
| File | Purpose |
|---|---|
| [file.h] | [what it defines] |
| [file.cpp] | [what it implements] |

Key classes:
| Class | Purpose |
|---|---|
| [ClassName] | [brief description] |

---

### [Module 2]

Location: [path]
Responsibility: [brief description]

(Same structure as above.)

---

## Public API surface

<!-- SETUP: List all public headers and the symbols they export. -->

| File | Exported symbols |
|---|---|
| [header.h] | [class names, function names] |

---

## Test inventory

<!-- SETUP: List test files and what they cover. -->

| File | Covers |
|---|---|
| [test_file.cpp] | [module or feature] |
