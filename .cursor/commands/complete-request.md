# Command: complete-request
# File: .cursor/commands/complete-request.md
# Type: developer command
# Activates: Memory writer

> Finalize a completed request after all its tasks are done:
> move the request card to the archive folder, write request summary.
> Run this after all tasks linked to the request have been finalized with complete-task.

---

## Usage

```
complete-request: request-NNN
```

---

## Pre-condition

Every task card linked to request-NNN must have `Status: done` and be archived
to `.cursor/tasks/archive/request-NNN/`. The archive folder is created by complete-task.

Do not run if any linked task is still active.

---

## What happens

### Step 1: Verify all linked tasks are done

Grep active task cards for the request number:

```bash
grep -l "Request: request-NNN" .cursor/tasks/active/*.md
```

Expected output: empty. If any files are listed — those tasks are still active.
Run `complete-task: task-NNN` for each before proceeding.

### Step 2: Verify archive folder exists

```bash
ls .cursor/tasks/archive/request-NNN/
```

Expected: task card(s), `sessions/`, `decisions/` already present from complete-task runs.

If the folder does not exist → complete-task was never run for this request. Stop.

### Step 3: Write request summary (Memory writer)

Memory writer appends to `.cursor/memory/decisions/adr-log.md`:

```markdown
## Request NNN: <title> — completed <date>
Tasks: task-NNN, task-MMM, ...
Summary: <one or two sentences — what the request delivered as a whole>
```

Write only what is non-obvious from the individual task summaries already present.
If the request had one task and the task summary is sufficient — write "see task-NNN summary".

### Step 4: Move the request card

[CRITICAL] File move is a developer filesystem action — not a Memory writer action.

```bash
mv .cursor/tasks/inbox/request-NNN.md  .cursor/tasks/archive/request-NNN/
```

### Step 5: Verify archive folder is complete

```bash
ls .cursor/tasks/archive/request-NNN/
```

Expected contents:
- `request-NNN.md` (just moved)
- `task-NNN-<slug>.md` for each linked task
- `sessions/` with all session files for all tasks
- `decisions/` with all decision files for all tasks

### Step 6: Verify inbox is clean

```bash
ls .cursor/tasks/inbox/
```

Confirm `request-NNN.md` is no longer present.

### Step 7: Report

```
complete-request: request-NNN done

Tasks completed: task-NNN [, task-MMM, ...]

Archived at: .cursor/tasks/archive/request-NNN/
  request-NNN.md
  task-NNN-<slug>.md
  sessions/task-NNN-plan.md
  sessions/task-NNN-impl.md
  sessions/task-NNN-env.md
  decisions/task-NNN-plan.md
  decisions/task-NNN-review.md
  <all additional task files for multi-task requests>

Inbox remaining: <list of remaining request files, or "empty">
```

---

## When to run

After all tasks linked to request-NNN have been finalized with complete-task.
Do not run while any linked task has Status != done.

---

## Acceptance checklist

- [ ] Active grep returned empty — all tasks done (Step 1)
- [ ] Archive folder exists with task files (Step 2)
- [ ] Request summary written to `adr-log.md` (Step 3)
- [ ] `request-NNN.md` moved from inbox to archive (Step 4)
- [ ] Archive folder listing confirms all expected files present (Step 5)
- [ ] Inbox verified — `request-NNN.md` no longer present (Step 6)
