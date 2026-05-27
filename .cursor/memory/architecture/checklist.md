# Architecture Compliance Checklist
# File: .cursor/memory/architecture/checklist.md
# Maintained by: Memory writer + Architect

> Used by: Architect, Critic, Reviewer
> Purpose: enforcement rules with severity levels for this project.
> Update when: architectural decisions add or change invariants.
>
> [SETUP] Fill in the project-specific checklist sections below.
> This file is created by the Architect during the first design task.
> Until populated: apply the rules from rules/arch.md only.

---

## Severity levels

| Marker | Meaning | Effect |
|---|---|---|
| [ERROR] | Invariant violation — must be fixed | [BLOCKING] — loop cannot complete, PR cannot merge |
| [WARN] | Deviation from convention | Must be documented and justified, non-blocking |
| [QUESTION] | Needs clarification before assessment | Loop pauses until resolved |

---

## 1. Pre-work (mandatory before any non-trivial change)

- [ ] `memory/project/brief.md` reviewed — scope and non-goals understood
- [ ] `memory/architecture/map.md` reviewed — invariants and boundaries understood
- [ ] `memory/architecture/inventory.md` reviewed — relevant sections identified
- [ ] Dependency analysis performed — see `skills/dep-analysis.md`

[ERROR] Proceeding without completing pre-work.

---

## 2. Scope and boundary compliance

<!-- SETUP: Fill in the scope rules for this project. -->

- [ ] No out-of-scope logic added to the core library
- [ ] Public API changes are intentional and documented

[ERROR] Adding out-of-scope logic to the core library.

---

## 3. Layer rules

<!-- SETUP: Fill in the layer compliance rules specific to this project.
     These come from the layer dependency rules in map.md. -->

- [ ] No forbidden layer dependency introduced
- [ ] Lower layer does not modify state owned by upper layer

[ERROR] Forbidden layer dependency introduced.

---

## 4. Performance rules (if hot paths exist)

<!-- SETUP: Fill in performance rules or remove this section. -->

- [ ] No new heap allocation in hot paths
- [ ] No new virtual dispatch in tight loops
- [ ] No new logging or I/O in hot paths

[ERROR] Heap allocation introduced in hot path.

---

## 5. Determinism rules (if determinism required)

<!-- SETUP: Fill in determinism rules or remove this section. -->

- [ ] No `std::unordered_map` / `std::unordered_set` iteration in decision paths
- [ ] No pointer values as sort keys in decision paths
- [ ] `std::sort` on equal elements uses stable tie-breaking key

[ERROR] Non-deterministic iteration in decision path.

---

## 6. Public API rules

- [ ] ABI impact assessed for every public header change
- [ ] Breaking changes have developer approval and ADR
- [ ] New public symbols have documentation

[ERROR] Breaking ABI change without approval.
