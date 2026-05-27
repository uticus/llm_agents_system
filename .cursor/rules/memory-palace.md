# Rules: Memory Palace
# File: .cursor/rules/memory-palace.md
# Applied by: all agents

> Defines when to use the memory-palace MCP, what is forbidden, and what it cannot replace.
> See `.cursor/skills/memory-recall.md` for HOW to run a recall query.
> See `.cursor/mcp/memory-palace.md` for tool reference and content structure.

---

## When to use memory-palace

- **Orientation before analysis:** call `memory_recall` once at the start of a session,
  before reading mandatory files, to surface relevant prior decisions, warnings, and facts.
- **Cross-session context:** when resuming a task after a context break to recall what was
  established in prior sessions without re-reading full memory files.
- **Link discovery:** when a concept may be related to a prior ADR or architectural fact
  and adr-log.md was not yet read.

---

## When NOT to use memory-palace

| Need | Use instead |
|---|---|
| Symbol definition, call sites, inheritance | Serena (`find_symbol`, `get_symbols_overview`) |
| Current build facts, preset names, paths | `.cursor/memory/project/build.md` |
| Authoritative ADR history | `.cursor/memory/decisions/adr-log.md` |
| Current module boundaries and invariants | `.cursor/memory/architecture/map.md` |
| Current component inventory | `.cursor/memory/architecture/inventory.md` |
| String literals, log messages, comments in code | Grep |

---

## Policy: palace-first for orientation, files for authority

1. Run `memory_recall` once per session before mandatory reads.
2. Use recall results to narrow which mandatory files to read first.
3. Always read the relevant markdown memory file or task card section before acting on a
   recalled fact. Recall surfaces context — the markdown files are authoritative.
4. If recall returns no relevant result — proceed with mandatory file reads as normal.
   Do not retry with broader queries to find an answer that may not exist.

---

## Forbidden patterns

- Treating recall results as authoritative without verifying against markdown memory files
- Skipping mandatory reads because a recall result appears to answer the question
- Writing to memory-palace from any agent role other than Memory writer
- Running recall queries mid-task instead of at session start (except when explicitly
  resuming after a context break)
- Archiving palace entries without Memory writer direction
- Using `memory_reflect` (LLM synthesis over recalled entries) as a substitute for reading
  source files — synthesis may hallucinate; source files are ground truth

---

## Centrality-weighting awareness

New palace entries rank below older entries with many connections and access counts.
If an expected entry is missing from top-3 recall results:
- Run a more specific query
- Use `memory_get` by known ID if the ID is available in session context
- Do not assume the entry does not exist

## Method-level entries (IDs 62–120)

Palace entries IDs 62–120 capture individual method purpose, parameters, and algorithmic notes (added task-039, 2026-04-26).
These entries may be queried at method granularity using method name + aspect noun phrases.
Use method-name + aspect queries (e.g., `"Execute target selection"`, `"ComputeUtility allocation budget"`, `"GetCountryStatesAccessor null check"`) for method-level recall.
Increase n_results to 5 when querying method-level entries, as new entries rank lower than older foundational entries due to centrality weighting.
