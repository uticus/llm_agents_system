# Skill: Memory Distillation
# File: .cursor/skills/memory-write.md
# Used by: Memory writer

> Algorithm for extracting durable knowledge from session content
> and writing it into project memory.
> Goal: produce concise, factual, non-redundant memory entries.

---

## Core principle

Memory is not a log. Memory is ground truth.
Write only what future agents need to know to make correct decisions.
If in doubt whether something belongs in memory — it probably belongs in the session file.

---

## Algorithm

### Phase 1: Classify the source content

Read the source file. For each piece of content, classify it:

| Class | Write to memory? | Destination |
|---|---|---|
| Confirmed architectural decision | Yes | `memory/decisions/adr-log.md` |
| Changed module boundary or invariant | Yes | `memory/architecture/map.md` |
| New or renamed component | Yes | `memory/architecture/inventory.md` |
| Changed enforcement rule | Yes | `memory/architecture/checklist.md` |
| Stable project fact (build, API, constraint) | Yes | `memory/project/<relevant>.md` |
| Alternative considered but rejected | No — stays in session | — |
| Hypothesis not yet confirmed | No — stays in session | — |
| Implementation detail | No — stays in session | — |
| In-loop discussion or iteration | No — stays in session | — |
| Warning or open question | No — stays in session (or task card §open-questions) | — |

### Phase 2: Check for existing entries

Before writing, search the target file for:
- Same topic already documented → do not duplicate, reference instead
- Contradicting entry → surface to developer, do not overwrite silently
- Superseded entry → mark old entry, append new one

### Phase 3: Distill

Rewrite the content in memory style:
- Factual, declarative sentences
- Present tense ("Module X owns Y" not "We decided that X should own Y")
- No hedging ("must", "always", "never" — not "should", "typically", "usually")
- No first-person ("The decision was made" not "We decided")
- Maximum 3-5 sentences per entry
- Reference the ADR or task card for full context

Before / after example:

```
BEFORE (session content):
"After a lot of discussion we decided that it probably makes more sense to use
a flat array instead of std::map for the unit lookup because of performance,
though we weren't 100% sure about the edge cases with duplicate IDs."

AFTER (memory entry):
"Unit lookup uses a flat sorted array. std::map is forbidden in this path
due to hot-path allocation constraint (see rules/hotpath.md). Duplicate ID
handling: see ADR-007."
```

### Phase 4: Assign location

| Content type | File | Location within file |
|---|---|---|
| ADR | `memory/decisions/adr-log.md` | Append at end, next ADR-NNN |
| Map change | `memory/architecture/map.md` | Update relevant section + append to §Evolution log |
| Inventory addition | `memory/architecture/inventory.md` | Add row to relevant layer table |
| Checklist change | `memory/architecture/checklist.md` | Update relevant section |
| Project fact | `memory/project/<file>.md` | Update relevant section |

### Phase 5: Write and confirm

Write the entry. Then re-read the surrounding context to verify:
- No sentence contradicts an adjacent entry
- The entry is self-contained — a reader unfamiliar with the session understands it
- The entry references the source (task card or ADR) for traceability

---

## ADR distillation guide

When distilling an ADR from session content:

1. **Context**: what problem required a decision? (1-2 sentences)
2. **Decision**: what was chosen? (1 sentence, declarative)
3. **Alternatives**: what was considered and why rejected? (bullet per alternative)
4. **Consequences**: what does this enable or constrain going forward?
5. **Constraints imposed**: what must Implementer follow as a result?

Do not include: the debate, the iteration history, individual opinions, or maybes.

---

## Quality checks

Before finalizing any memory entry:

- [ ] Written in declarative, present-tense English
- [ ] No hedging language ("should", "typically", "probably")
- [ ] No alternatives or hypotheses — only the confirmed decision
- [ ] Self-contained — readable without the source session
- [ ] References source (task-NNN or ADR-NNN) for traceability
- [ ] No duplicate of existing entry in the same file
- [ ] No contradiction with existing entries in the same file
