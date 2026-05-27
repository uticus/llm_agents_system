# Command: memory-update
# File: .cursor/commands/memory-update.md
# Type: developer command
# Activates: Memory writer

> Explicitly trigger Memory writer to persist knowledge
> from a session or decision file into permanent memory.

---

## Usage

```
memory-update: <source file> → <target memory file>
memory-update: <description of what to persist>
```

## Examples

```
memory-update: tasks/sessions/task-001-plan.md → memory/decisions/adr-log.md
memory-update: tasks/decisions/task-001-review.md → memory/architecture/inventory.md
memory-update: persist arch decisions from task-001 design session
memory-update: update inventory — task-002 created ai3NewEvaluator
```

## What happens

1. Memory writer reads source file
2. Memory writer reads target memory file — checks for duplicates and contradictions
3. Memory writer distills confirmed facts — does not transcribe
4. Memory writer writes to target and updates `memory/status.md`
5. Memory writer reports what was written

## When to use

- After CP2: persist ADR decisions from design session
- After CP5: update inventory and map with new components
- When a session reveals architectural facts worth keeping long-term
- When `memory/status.md` shows a file as "not yet created" but it should exist

## Notes

- Memory writer writes only to `memory/**` and `tasks/decisions/**`
- If source content contradicts existing memory:
  Memory writer surfaces the conflict — developer resolves before writing
- Full algorithm: `skills/memory-write.md`
