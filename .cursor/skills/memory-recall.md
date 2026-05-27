# Skill: Memory Palace Recall
# File: .cursor/skills/memory-recall.md
# Used by: all agents (orientation step at session start)

> HOW to run a memory-palace recall query.
> WHEN to use it and what is forbidden: see `.cursor/rules/memory-palace.md`.
> Tool reference and content structure: see `.cursor/mcp/memory-palace.md`.

---

## When to run recall

Once per session, before reading mandatory files. This is an orientation step — not a
replacement for reading the relevant markdown memory files or task card.

---

## Tool call

```
mcp__memory-palace__memory_recall
  query: "<short noun phrase describing the component or question>"
  n_results: 3   (default; sufficient for orientation)
```

---

## Query formulation

Use a short noun phrase: component name + relevant aspect. Avoid questions or sentences.

| Good query | Why |
|---|---|
| `"<ModuleName> interface fields"` | specific component + aspect |
| `"<ClassName> scoring algorithm"` | class name + relevant pattern |
| `"<Interface> mutation path"` | interface + role |
| `"<Subsystem> two-pass distribution"` | subsystem + pattern name |
| `"<PlanType> hot path allocation"` | component + constraint area |

Avoid:
- Vague queries: `"architecture"`, `"module"`, `"memory"` — too broad, returns high-centrality
  generic entries
- Question form: `"how does X work?"` — phrase as noun: `"X allocation pattern"`

---

## Result evaluation

For each of the top-3 entries returned:
1. Read the `content` field summary (one or two sentences)
2. Note the `instance_id` and `tags` to confirm relevance
3. If the entry is relevant — note the key fact; verify it against the markdown memory file
   before acting on it
4. If no entry is relevant — proceed to mandatory file reads without further recall

Do not read all 3 entries in full. Skim for relevance.

---

## When entries are missing from top-3

New entries rank below older, more connected entries (centrality-weighted ranking).
If you expect a recent entry that does not appear:
- Run a more specific query (add more terms from the entry title)
- If the ID is known from session context: use `mcp__memory-palace__memory_get` with `id`
- Do not assume the entry does not exist

---

## Palace content reference

<!-- SETUP: After populating the memory palace for a new project, update this section
     with the actual entry count, ID ranges, instance IDs, and content areas.
     Until then, keep this as a placeholder. -->

Total entries: 0 (not yet populated for this project)

| ID range | Content area | instance_id |
|---|---|---|
| — | — | — |

### Registered instance IDs

<!-- SETUP: Add rows as memory palace entries are created. -->

| instance_id | Content area |
|---|---|
| project | Project-wide facts |

### Tag vocabulary

| Tag | Meaning |
|---|---|
| `adr` | Architectural Decision Record |
| `architecture` | Architectural fact or invariant |
| `design_decision` | Implementation-level decision |
| `api_contract` | Interface/contract specification |
| `gotcha` | Non-obvious behavior or trap |
| `analysis` | Analysis finding or summary |
| `debt` | Technical debt item |
| `test_pattern` | Testing pattern or infrastructure |
