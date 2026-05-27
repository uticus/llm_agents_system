# Command: complete-task
# File: .cursor/commands/complete-task.md
# Type: developer command
# Activates: Memory writer

> Finalize a single completed task after CP5 approval:
> persist knowledge, archive all task files, update status.
> Run this after developer approves merge at CP5.
> One task at a time. Run complete-request after all tasks for the request are done.

---

## Usage

```
complete-task: task-NNN
```

The linked request number is read from the `Request:` field in the task card header.

---

## Pre-condition

Task card `Status:` must be one of:
- `implemented-awaiting-CP5` — standard implementation task (cpp / python / ml)
- `analysis-complete` — code-analyst task; developer has reviewed output artifacts at CP5

Developer has approved at CP5.
Do not run if CP5 resulted in "rework → loop / Analyst: Code" — task is not yet complete.

---

## What happens

### Step 1: Read task card

Identify from `.cursor/tasks/active/task-NNN-<slug>.md`:
- Task number (NNN) and slug
- Linked request number (from `Request:` field in task card header)

The request number is required. If `Request:` is missing from the task card — stop and ask
the developer for the request number before proceeding.

### Step 2: Persist knowledge (Memory writer)

Call Memory writer to distill session and decision files.

**Standard implementation task (cpp / python / ml):**
- `sessions/task-NNN-plan.md` → `.cursor/memory/decisions/adr-log.md`
  (if architectural decisions were made in design loop)
- `decisions/task-NNN-review.md` → `.cursor/memory/architecture/inventory.md`
  (if new components were created)
- `sessions/task-NNN-impl.md` → `.cursor/memory/architecture/map.md`
  (if implementation revealed new architectural facts)

**code-analyst task:**
- `sessions/task-NNN-plan.md` → `.cursor/memory/decisions/adr-log.md`
  (if architectural decisions were made in design loop)
- `sessions/task-NNN-analysis.md` → `.cursor/memory/architecture/inventory.md` and/or `map.md`
  (analysis findings that update structural knowledge)
Note: `sessions/task-NNN-env.md` and `sessions/task-NNN-impl.md` do not exist for code-analyst tasks.

Memory writer reads each source, extracts confirmed decisions and facts,
appends to target files. Does not transcribe — distills.

### Step 3: Update status.md

Memory writer updates `.cursor/memory/status.md`:
- Mark any newly created memory files as "created"
- Add "last updated" date to files that were updated

### Step 4: Write task summary

Memory writer appends to `.cursor/memory/decisions/adr-log.md`:

```markdown
## Task NNN: <title> — completed <date>
Implemented: <one sentence>
ADRs produced: ADR-NNN, ... | none
Components added: <list from inventory> | none
Key decisions: <list or "none beyond ADRs">
```

### Step 5: Archive task files

[CRITICAL] File moves are a developer filesystem action — not a Memory writer action.

**5a. Update task card status before archiving:**

Open `.cursor/tasks/active/task-NNN-<slug>.md` and change `Status:` to `done`.

**5b. Create archive subdirectories if they do not exist:**

```bash
mkdir -p .cursor/tasks/archive/request-MMM/sessions
mkdir -p .cursor/tasks/archive/request-MMM/decisions
```

Where `request-MMM` is the value from the task card's `Request:` field.

**5c. Move all task files — three operations:**

```bash
# 1. Task card
mv .cursor/tasks/active/task-NNN-<slug>.md         .cursor/tasks/archive/request-MMM/

# 2. Session files
mv .cursor/tasks/sessions/task-NNN-*.md            .cursor/tasks/archive/request-MMM/sessions/

# 3. Decision files
mv .cursor/tasks/decisions/task-NNN-*.md           .cursor/tasks/archive/request-MMM/decisions/
```

**5d. Verify — confirm no task-NNN files remain outside archive:**

```bash
find .cursor/tasks/active .cursor/tasks/sessions .cursor/tasks/decisions -name "task-NNN-*"
```

Expected output: empty. If any files are listed — they were not moved. Move them before proceeding.

### Step 6: Report

```
complete-task: task-NNN done

Memory persisted:
  adr-log.md:    <what was added or "nothing new">
  inventory.md:  <what was added or "nothing new">
  map.md:        <what was updated or "no changes">

Archived to: .cursor/tasks/archive/request-MMM/
  task-NNN-<slug>.md
  sessions/task-NNN-plan.md
  sessions/task-NNN-impl.md     (cpp/python/ml tasks)
  sessions/task-NNN-env.md      (cpp/python/ml tasks)
  sessions/task-NNN-analysis.md (code-analyst tasks)
  decisions/task-NNN-plan.md
  decisions/task-NNN-review.md  (cpp/python/ml tasks)

Active tasks remaining for request-MMM: <N>
  <list remaining active task card filenames, or "none — run complete-request: request-MMM">
```

---

## When to run

After developer approves merge at CP5 and the branch is merged.
Do not run if CP5 resulted in "rework → loop".

---

## What NOT to archive here

- Files belonging to other active tasks (different task number)
- The request card (`inbox/request-MMM.md`) — archived by complete-request, not this command

---

## Acceptance checklist

- [ ] Task card `Request:` field read — request number identified
- [ ] Memory writer called for Steps 2–4
- [ ] `status.md` updated
- [ ] Task summary appended to `adr-log.md`
- [ ] `Status: done` set in task card before moving (Step 5a)
- [ ] Archive subdirs created: `archive/request-MMM/sessions/` and `archive/request-MMM/decisions/` (Step 5b)
- [ ] All three move operations executed: task card + sessions + decisions (Step 5c)
- [ ] Verification find returned empty (Step 5d)
- [ ] Report shows count and list of remaining active tasks for this request
