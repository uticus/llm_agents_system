# Command: checkpoint
# File: .cursor/commands/checkpoint.md
# Type: developer command

> Show the current status of one or all active task cards.

---

## Usage

```
checkpoint: task-NNN
checkpoint: all
```

## What happens

Reads `tasks/active/task-NNN.md` and latest session files.
Produces a status summary without activating any agent.

## Output — single task

```
## Checkpoint: task-NNN <title>

Phase:   <1–5>
Status:  in progress | waiting for CP | blocked | ready for CPN
CP next: CP1 | CP2 | CP3 | CP4 | CP5 | done

Sections:
  §request:       done | in progress | not started
  §decomposition: done | in progress | not started
  §architecture:  done | in progress | not started
  §plan:          done | in progress | not started
  §spec:          done | in progress | not started
  §test-criteria: done | in progress | not started

Last action: [AgentName] <what happened>

Blockers: none | <list>

Next: <specific action for developer>
```

## Output — all tasks

```
checkpoint: all

task-001-eval-cache:    phase 5 — awaiting CP5
task-002-new-plan-type: phase 2 — design loop iteration 3
task-003-python-api:    phase 3 — spec in progress
```
