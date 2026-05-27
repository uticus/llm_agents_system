# MCP Registry
# File: .cursor/mcp/registry.md

> Authoritative list of connected MCP servers.
> Maintained by the developer. Agents read this file to discover available tools.
> Each server has a dedicated file in `.cursor/mcp/<name>.md` with methods and usage patterns.
> When no MCP server fits a task — fall back to text search, but document why.

---

## Connected servers

| Name | File | Purpose | Use when |
|---|---|---|---|
| Serena | `.cursor/mcp/serena.md` | Structural code analysis: symbol discovery, reference search, pattern search | Searching for symbols, call sites, references, bindings, export macros |
| memory-palace | `.cursor/mcp/memory-palace.md` | Semantic memory: structured entries for ADRs, architecture, components, patterns; recall before mandatory file reads for orientation; memory-writer mirrors all markdown memory writes | Orientation recall at session start; linking related concepts; cross-session context recall |

---

## Tool priority policy

When performing any search or discovery task, follow this order:

1. MCP structural tools — for symbols, references, call sites, patterns in code structure
2. Text search (grep) — only for string literals, log messages, comments, and content
   not detectable by structural analysis

Never substitute structural search with grep when an MCP tool can do the job.
Never run broad repo scans when a targeted structural query is available.

---

## Adding a new MCP server

When a new MCP server is connected:
1. Add a row to the table above
2. Create `.cursor/mcp/<name>.md` following the format of `serena.md`
3. Update `CLAUDE.md` table row: `MCP tools | see .cursor/mcp/registry.md`
4. Update relevant agent role files if the new server changes their tool priority
