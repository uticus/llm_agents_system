# Rules: Project Memory
# File: .cursor/rules/memory.md
# Applied by: Memory writer, all agents (read rules)

> Defines what belongs in permanent memory vs session files.
> Defines append and update rules for memory files.
> Agents read this to understand what they should flag for Memory writer.

---

## What goes into memory

Memory contains only:
- Confirmed architectural decisions (ADRs)
- Established module boundaries and invariants
- Stable project facts (build system, public API, key constraints)
- Structural inventory (components, their roles, their status)
- Enforcement rules and their severity levels

---

## What stays in session files

Session files contain:
- Iteration history (drafts, feedback, revisions)
- Alternatives considered and rejected
- Hypotheses and open questions
- In-loop discussion between agents
- Warnings that were not resolved
- Implementation details that do not affect architecture

Session files are not deleted after a task completes — they move to `tasks/archive/`.
They are the audit trail. Memory is the ground truth.

---

## Append-only rule

Memory files are append-only with one exception: superseding.

| Operation | Allowed | How |
|---|---|---|
| Append new entry | Yes | Add at end of relevant section |
| Update existing entry (factual correction) | Yes | Add corrected entry, mark old as `[corrected — see below]` |
| Supersede existing entry | Yes | Mark old as `[superseded by ADR-NNN]`, append new |
| Delete an entry | No | Never — use supersede instead |
| Reorder entries | No | Order reflects chronology |
| Overwrite without marker | No | Always leave trace of what changed |

---

## ADR threshold

An ADR is required when a decision:
- Changes a public interface or ABI
- Introduces a pattern not previously used in the project
- Explicitly trades off one quality attribute for another
- Overrides or supersedes an existing ADR
- Changes the canonical pipeline step order

An ADR is NOT required for:
- Routine implementation choices within established patterns
- Bug fixes that restore intended behavior
- Test additions that don't change public contracts

When in doubt — write an ADR. Over-documentation is safer than under-documentation.

---

## Memory file ownership

| File | Written by | Read by |
|---|---|---|
| `memory/project/brief.md` | Memory writer | All agents |
| `memory/project/domain.md` | Memory writer | Analyst, Architect, Test designer |
| `memory/project/game-mechanics.md` | Memory writer | Test designer, Architect |
| `memory/project/build.md` | Memory writer (from developer input) | Environment, Implementers |
| `memory/architecture/map.md` | Architect + Memory writer | Architect, Critic, Reviewer, Decomposer |
| `memory/architecture/inventory.md` | Memory writer (triggered by Architect/Implementer) | Architect, Reviewer, Decomposer |
| `memory/architecture/checklist.md` | Memory writer (triggered by Architect) | Architect, Critic, Reviewer |
| `memory/decisions/adr-log.md` | Memory writer (triggered by Architect) | Architect, Planner, Critic |

---

## Calling Memory writer

Any agent may call Memory writer. The call must include:
- Source: which file or content to distill
- Target: which memory file to update
- Content: what specifically to write (or "distill this section")

Memory writer does not act on implicit signals.
If an agent produces content that belongs in memory — it must explicitly call Memory writer.
After writing to any memory file — Memory writer updates `.cursor/memory/status.md`.

Agents that must call Memory writer:
- Architect: after every ADR-worthy decision, after every map.md change
- Any Implementer: after creating a new component or file
- Planner: after developer approves plan at CP2 (to write clean plan to decisions/)
- Reviewer + Tester: after loop stop condition met (to write review report to decisions/)

---

## Prohibited actions

- Writing to `memory/**` from any agent other than Memory writer
  (exception: Architect updates `task-NNN.md §architecture` — this is a task card, not memory)
- Writing hypotheses, alternatives, or unconfirmed content to memory
- Overwriting memory entries without a supersede marker
- Using memory files as a working scratchpad — use session files instead
- Reading memory files as immutable — they are updated by Memory writer as the project evolves
