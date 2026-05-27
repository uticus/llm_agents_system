# Command: arch-audit
# File: .cursor/commands/arch-audit.md
# Type: developer command
# Activates: Architect + Reviewer (read-only analysis mode)

> Full architectural audit of the codebase or a specific module.
> No task card required. Used for periodic health checks and pre-refactoring analysis.
> Does not modify code — produces a findings report only.

---

## Usage

```
arch-audit
arch-audit: <source-dir>/
arch-audit: <module or layer name>
```

## What happens

### Step 1: Load architectural baseline

Read:
- `memory/architecture/map.md` — invariants, layer boundaries, pipeline
- `memory/architecture/checklist.md` — enforcement rules and severity
- `memory/architecture/inventory.md` — known components and their layers

### Step 2: Scan target scope

For each file in scope, run `skills/arch-check.md`:
- Assign to architectural layer
- Check layer dependencies (forbidden inter-layer calls)
- Check plan-centricity (no direct execution from estimation/distribution)
- Check phase separation (no cross-phase leakage)
- Check hot-path compliance (allocation, I/O, virtual dispatch)
- Check determinism (unordered containers, unstable sort in decision paths)
- Check estimation layer purity (no side effects)

Use Serena MCP for structural search:
- `search_for_pattern` for forbidden patterns
- `find_referencing_symbols` for inter-layer dependency detection

### Step 3: Check inventory completeness

Compare found components against `memory/architecture/inventory.md`:
- Components in code not in inventory → [MISSING from inventory]
- Components in inventory not in code → [STALE in inventory]

### Step 4: Produce findings report

```markdown
# Architectural Audit Report
Date: <date>
Scope: <target>

## Summary
[ERROR] violations: N
[WARN]  issues:     M
Missing from inventory: K
Stale in inventory:    J

## [ERROR] Violations
### <file>:<line>
Invariant: <which rule from checklist.md>
Evidence:  <what the code does>
Severity:  BLOCKING

## [WARN] Issues
### <file>:<line>
Issue: <description>
Recommendation: <what to fix>

## Inventory gaps
### Missing from inventory
- <ClassName> in <file> — belongs to <layer>

### Stale in inventory
- <ClassName> — listed in inventory but not found in code

## Recommendations
<prioritized list of what to fix first>
```

---

## When to use

- Before starting a major refactoring
- After a large merge to verify no invariants were broken
- Periodically as a health check (monthly or per milestone)
- When `memory/architecture/map.md` has been updated and code needs verification

## Notes

- Audit is read-only — no code changes
- To update `map.md` after audit findings: use `commands/arch-map-update.md`
- To sync inventory after audit: use `commands/arch-inventory-sync.md`
- To fix violations: create a new task via `commands/new-task.md`
