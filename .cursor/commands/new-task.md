# Command: new-task
# File: .cursor/commands/new-task.md
# Type: developer command
# Activates: Analyst

> Start a new request. Analyst conducts a clarifying dialog
> and produces a confirmed request file.

---

## Usage

```
new-task: <free description of what you need>
```

Or just describe the request in natural language —
Analyst activates when a new request is detected.

## What happens

1. Analyst reads `CLAUDE.md`, `memory/project/brief.md`, `memory/project/domain.md`
2. Analyst asks clarifying questions — one topic at a time, max 2-3 per turn
3. Developer confirms the summary
4. Analyst writes `tasks/inbox/request-NNN.md`
5. Developer reviews at CP1 — go activates Decomposer

## Example

```
new-task: I want the AI to score combat phase targets
using unit HP and firepower to improve target selection.
```

## Notes

- Analyst does not split the request — Decomposer does that
- If request contains multiple independent changes, Analyst will flag it
- After Analyst finishes: check `tasks/inbox/` for the new file
