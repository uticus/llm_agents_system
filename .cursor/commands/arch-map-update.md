# Command: arch-map-update
# File: .cursor/commands/arch-map-update.md
# Type: developer command
# Activates: Architect + Memory writer

> Update `memory/architecture/map.md` to reflect the current state of the codebase.
> Used when architecture has changed significantly and documentation is out of date.
> All changes require developer confirmation — map.md is ground truth for all agents.

---

## Usage

```
arch-map-update
arch-map-update: <specific section to update>
arch-map-update: layers
arch-map-update: invariants
arch-map-update: pipeline
```

## What happens

### Step 1: Diff current map against code

Read `memory/architecture/map.md` in full.
For each claim in the map, verify against actual code:

**Layer boundaries:**
- Do claimed layer assignments match actual class locations?
- Are forbidden dependencies actually absent?
- Are allowed dependencies correct?

**Canonical pipeline:**
- Does the claimed step order match the actual orchestration entry point?
- Are all pipeline stages still present?

**Invariants:**
- Plan-centricity: does code actually route all execution through plans?
- Phase separation: are phase boundaries respected in implementation?
- Determinism: are stated determinism rules actually enforced?

Use Serena MCP for verification:
- `find_symbol` to locate key classes and confirm layer
- `find_referencing_symbols` to verify dependency directions
- `search_for_pattern` to check for invariant violations

### Step 2: Identify discrepancies

For each discrepancy between map and code:

```
Discrepancy: <section in map.md>
Map claims:  <what map.md says>
Code shows:  <what code actually does>
Type:        map is wrong | code violates map | map is outdated
```

Present all discrepancies to developer before making any changes.

### Step 3: Developer confirms what to update

For each discrepancy, developer decides:
- **Map is wrong** → update map to reflect current code
- **Code violates map** → create a task to fix the code (via `new-task`)
- **Map is outdated** → update map with new agreed architecture

Do not update map without explicit developer confirmation per discrepancy.

### Step 4: Update map.md (Memory writer)

Memory writer updates `memory/architecture/map.md`:
- Update affected sections
- Append to `§Architecture evolution log`:

```markdown
| <date> | <what changed> | <reason — code changed or map was wrong> |
```

- If change reflects a new architectural decision → create ADR entry in `adr-log.md`

### Step 5: Confirm

Report to developer:
```
arch-map-update: complete

Updated sections:
  §<section>: <what changed>

Evolution log: entry added
ADR: ADR-NNN created | none required

Recommend running arch-inventory-sync to keep inventory consistent.
```

---

## When to use

- After completing a major architectural refactoring
- When `arch-audit` reveals that map.md is out of date
- When a new module or layer is added
- When the canonical pipeline order changes

## Notes

- Never update map.md to paper over a code violation — fix the code instead
- Every map.md update is recorded in §Architecture evolution log
- Significant changes require an ADR — Architect decides threshold
