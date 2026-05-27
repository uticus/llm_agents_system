# Memory Palace MCP
# File: .cursor/mcp/memory-palace.md

> Semantic memory server for cross-session knowledge persistence.
> Stores structured entries (ADRs, architecture facts, component summaries, patterns) and
> supports semantic recall at session start.
> For usage rules and query formulation: see `.cursor/skills/memory-recall.md`.

---

## When to use memory-palace

| Task | Use memory-palace | Use markdown memory files |
|---|---|---|
| Orientation recall at session start | yes | as cross-check |
| Looking up a specific component known to be in palace | yes | no |
| Reading authoritative architectural decisions | no | yes (`memory/decisions/adr-log.md`) |
| Reading project structure | no | yes (`memory/architecture/map.md`) |
| Persisting new knowledge after a task | via Memory writer | yes (primary) |

---

## Tool API

### memory_recall
Semantic similarity search over all entries.

```
mcp__memory-palace__memory_recall
  query: str        # short noun phrase (see memory-recall.md for guidance)
  n_results: int    # default 3, max 10
```

Returns: list of entries ordered by relevance, each with `id`, `content`, `tags`, `instance_id`.

### memory_get
Retrieve a specific entry by ID.

```
mcp__memory-palace__memory_get
  id: int           # exact entry ID
```

Returns: full entry content.

### memory_store
Store a new entry (used by Memory writer only).

```
mcp__memory-palace__memory_store
  content: str      # entry text — concise, self-contained, specific
  instance_id: str  # registered instance ID (see below)
  tags: list[str]   # from tag vocabulary
```

Returns: assigned entry ID.

---

## Entry content guidelines

Each entry must be:
- Self-contained — readable without the file it summarizes
- Specific — one component or one decision, not a module overview
- Concise — 1-5 sentences
- Action-oriented — what must an implementer know about this?

Good: "ai3MovementEstimator.GetCost() — caches results in m_cache; invalidated in BeginTurn(). O(N) population on first call per turn. Hot path: do not resize or reallocate inside GetCost()."
Bad: "ai3MovementEstimator handles movement estimation."

---

## Registered instance IDs

<!-- SETUP: Update this table as memory palace entries are created for the project.
     Until populated, the palace is empty. -->

| instance_id | Content area |
|---|---|
| project | Project-wide facts and ADRs |

Add new instance IDs here when Memory writer registers new component areas.

---

## Tag vocabulary

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

---

## Palace content reference

<!-- SETUP: Update this section after memory palace entries are created.
     Until then the palace is empty for this project. -->

Total entries: 0 (not yet populated for this project)

| ID range | Content area | instance_id |
|---|---|---|
| — | — | — |
