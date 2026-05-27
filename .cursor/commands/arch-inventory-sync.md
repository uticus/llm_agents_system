# Command: arch-inventory-sync
# File: .cursor/commands/arch-inventory-sync.md
# Type: developer command
# Activates: Memory writer

> Synchronize `memory/architecture/inventory.md` with the current codebase.
> Finds new components not yet in inventory and stale entries for removed components.
> All changes require developer confirmation.

---

## Usage

```
arch-inventory-sync
arch-inventory-sync: <source-dir>/
arch-inventory-sync: <layer name>
```

## What happens

### Step 1: Scan codebase for components

Scan target scope for all architectural components:

```
For each .h file in <source-dir>/ and <include-dir>/:
  Find class declarations
  Determine:
    - Class name
    - Architectural layer (from naming convention and dependencies)
    - Responsibility (from class docstring or context)
    - Status: active | legacy | stub
```

Use Serena MCP:
```
mcp_serena_search_for_pattern(pattern: "class ai3")
mcp_serena_search_for_pattern(pattern: "class XAI")
mcp_serena_find_symbol(symbol_name: "ai3", symbol_type: "class")
```

### Step 2: Compare against inventory

Read `memory/architecture/inventory.md`.

Build two lists:

**Missing from inventory** — found in code, not in inventory:
```
| ClassName | File | Layer | Responsibility (inferred) |
```

**Stale in inventory** — in inventory, not found in code:
```
| ClassName | Last known file | Likely removed or renamed |
```

**Changed** — in both, but description may be outdated:
```
| ClassName | Inventory says | Code shows |
```

### Step 3: Present to developer

Show all three lists. Ask developer to confirm for each:

For **missing**: "Add to inventory under [layer]?" → yes / no / wrong layer
For **stale**: "Mark as removed?" → yes / no / renamed to [X]
For **changed**: "Update description?" → yes / provide new description / skip

Do not modify inventory without explicit per-entry confirmation.

### Step 4: Update inventory (Memory writer)

Memory writer updates `memory/architecture/inventory.md`:

- **Add** new entries to correct layer table
- **Mark** removed entries: append `[NOTE: removed — <date>]`
- **Mark** renamed entries: update name, add `[NOTE: renamed from X — <date>]`
- **Update** changed descriptions

Memory writer appends to `memory/status.md`:
```
| memory/architecture/inventory.md | updated | <date> | sync with codebase |
```

### Step 5: Confirm

Report to developer:
```
arch-inventory-sync: complete

Added:   N new components
Removed: M stale entries marked
Updated: K descriptions

Inventory now reflects codebase state as of <date>.
```

---

## When to use

- After completing a task that created new components (`complete-task` reminder)
- After `arch-audit` reveals inventory gaps
- After `arch-map-update` changes layer structure
- Periodically when active architectural redesign is ongoing
- Before starting `arch-audit` — ensures baseline is accurate

## Status markers

Components in inventory use these markers (see `memory/architecture/inventory.md §status legend`):

| Marker | Meaning |
|---|---|
| *(no marker)* | Active, stable, in use |
| `[NOTE: legacy]` | Exists, works, do not extend |
| `[NOTE: stub]` | Declared but not fully implemented |
| `[NOTE: new]` | Added in current architectural redesign |
| `[NOTE: removed — date]` | No longer exists in code |
| `[NOTE: renamed from X — date]` | Renamed, traceability preserved |

## Notes

- Sync is read-only on code — only inventory.md changes
- Never remove an inventory entry — mark as removed instead (traceability)
- Naming convention `ai3*` identifies AI layer components
- If a class cannot be assigned to a layer → flag to Architect before adding
