# Agent Pipeline

> This document is the authoritative description of the multi-agent pipeline.
> All agents read this file as part of their mandatory context load.
> Language: English only in all project files.
> No emojis. Use plain markers: [CRITICAL], [WARNING], [OK], [ERROR].

---

## 1. Pipeline overview

The pipeline transforms a developer request into verified, reviewed, documented code
through a sequence of specialized agents organized into five phases.

Each phase produces file artifacts consumed by the next phase.
Parallel directions (multiple task cards) run independently through the same pipeline.
The developer retains full control: every phase ends with a checkpoint requiring explicit go.

### Core principles

- Context isolation: each agent reads only what it needs. No global shared context.
- File-based handoff: agents communicate through files, not through shared conversation state.
- Dual memory: every agent writes a session draft (live log) and a clean final artifact.
- Feedback loops: Design and Implementation phases are iterative loops, not linear steps.
- Memory writer is cross-cutting: called as needed at any phase to persist knowledge.
- Developer checkpoints: five explicit stops where the developer reviews and approves.

---

## 2. Pipeline model

```
1 — understand
  Analyst  ──►  Decomposer  ──►  [CP1] developer: review task cards → go
     ▲________________|
     developer: clarify / split differently

2 — design  (per task card, loop)
                                  [CP2] developer: approve plan → go
  Architect ──► Planner ──► Critic
      ▲              ▲__________|  feedback: revise plan
      |_________________________|  feedback: arch issue
  stop: Architect + Planner + Critic agreed
        └──────────────────────────────► CP2

3 — specify  (per task card)
  Spec writer ──► Test designer  ──►  [CP3] developer: review spec + tests → go
       ▲________________|
       feedback: clarify spec

4 — prepare environment
  Environment  ──►  [CP4] developer: verify env → go

5 — implement  (per task card, loop)
  C++ impl ┐
  Py  impl ├──► Reviewer ──► Tester
  ML  impl ┘       │              │
      ▲            │ feedback     │ fail → fix
      |____________|______________|
  stop: Reviewer + Tester agreed — ready
        └──────────────────────────► [CP5] developer: merge / rework → loop

  Analyst: Code  (code-analyst tasks only — phases 3 and 4 are skipped)
  └──────────────────────────────► [CP5] developer: review artifacts → go

  Memory writer: called as needed at any phase
  └──► memory/** + decisions/**
```

---

## 3. Checkpoints

| # | After | Developer action | Options |
|---|---|---|---|
| CP1 | Decomposer | Review task cards | go / edit / send back to Analyst |
| CP2 | Planner+Critic+Architect loop | Approve plan | go / revise → loop |
| CP3 | Spec writer + Test designer | Review spec and test criteria | go / adjust |
| CP4 | Environment | Verify build environment | go / fix env |
| CP5 | Reviewer + Tester | Review implementation | merge / rework → loop / escalate to CP2 |

---

## 4. Agent table

### Phase 1 — understand the request

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Analyst** | Conducts dialog with the developer. Asks clarifying questions. Does not finish until the request is unambiguous. | `CLAUDE.md` `memory/project/brief.md` `memory/project/domain.md` | `tasks/inbox/request.md` (draft) | `skills/dialog.md` | `rules/dialog.md` |
| **Decomposer** | Splits the request into independent task cards. Each card is a self-contained unit of work with isolated context. | `tasks/inbox/request-NNN.md` `.cursor/memory/project/brief.md` `.cursor/memory/architecture/map.md` | `tasks/active/task-NNN.md` ×N | `skills/decompose.md` | `rules/decompose.md` |

### Phase 2 — design (per task card, loop)

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Architect** | Makes architectural decisions. Updates architecture documentation. Participates in the loop — receives feedback from Critic and revises decisions. | `tasks/active/task-NNN.md` `.cursor/memory/architecture/map.md` `.cursor/memory/architecture/inventory.md` `.cursor/memory/decisions/adr-log.md` | `task-NNN.md §architecture` `.cursor/memory/architecture/map.md` (update) | `skills/arch-decision.md` | `rules/arch.md` `rules/no-deps-touch.md` |
| **Planner** | Produces a step-by-step implementation plan based on architectural decisions. Iterates with Critic until both agree. | `task-NNN.md §architecture` `.cursor/memory/decisions/adr-log.md` | `sessions/task-NNN-plan.md` (draft) `task-NNN.md §plan` (draft) | `skills/planning.md` | `rules/planning.md` |
| **Critic** | Attacks the plan. Finds gaps, risks, architecture violations, uncovered cases. Returns feedback to Planner or Architect. Agrees only when no blocking issues remain. | `sessions/task-NNN-plan.md` `.cursor/memory/architecture/map.md` `.cursor/memory/architecture/checklist.md` | `sessions/task-NNN-plan.md` (append) | `skills/critique.md` | `rules/critic.md` |

### Phase 3 — specify (per task card)

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Spec writer** | Translates the approved plan into a precise implementation specification for the Implementer. Iterates with Test designer if the spec is underspecified. | `task-NNN.md §plan` `.cursor/memory/architecture/map.md` | `task-NNN.md §spec` | `skills/spec-writing.md` | `rules/spec.md` |
| **Test designer** | Defines test scenarios, acceptance criteria, metrics, and edge cases. Can send feedback to Spec writer if the spec is incomplete. | `task-NNN.md §spec` `.cursor/memory/project/domain.md` | `task-NNN.md §test-criteria` | `skills/test-design.md` | `rules/testing.md` `rules/determinism.md` |

### Phase 4 — prepare environment

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Environment** | Prepares the build environment, dependencies, stubs, and scaffolding. Does not touch fetched dependencies. | `task-NNN.md §spec` `task-NNN.md §test-criteria` `.cursor/memory/project/build.md` | `sessions/task-NNN-env.md` build config, stubs | `skills/env-setup.md` | `rules/no-deps-touch.md` `rules/build.md` |

### Phase 5 — implement (per task card, loop)

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Impl: C++** | Implements the task in C++ following the spec. Logs progress to session file. Iterates based on Reviewer and Tester feedback. | `task-NNN.md §spec` `task-NNN.md §test-criteria` `sessions/task-NNN-env.md` | code in repo / git branch `sessions/task-NNN-impl.md` (draft) | `skills/impl-cpp.md` `skills/dep-analysis.md` | `rules/cpp.md` `rules/hotpath.md` `rules/abi.md` `rules/no-deps-touch.md` |
| **Impl: Python** | Implements the task in Python and pybind11 following the spec. Bindings are part of the public API. | `task-NNN.md §spec` `task-NNN.md §test-criteria` `sessions/task-NNN-env.md` | code in repo / git branch `sessions/task-NNN-impl.md` (draft) | `skills/impl-python.md` `skills/pybind.md` | `rules/python.md` `rules/bindings.md` |
| **Impl: ML** | Implements ML components following the spec. Ensures deterministic behavior and metric compliance. | `task-NNN.md §spec` `task-NNN.md §test-criteria` `sessions/task-NNN-env.md` | code in repo / git branch `sessions/task-NNN-impl.md` (draft) | `skills/impl-ml.md` `skills/metrics.md` | `rules/ml.md` `rules/determinism.md` |
| **Analyst: Code** | Executes structural code analysis tasks: reads code via Serena, produces markdown artifacts (memory files, reports, documentation). No C++ or Python source is modified. Phases 3, 4, and the Reviewer+Tester loop are skipped for this type. Pipeline shortcut: CP2 → Analyst: Code → CP5. | `task-NNN.md §architecture` `task-NNN.md §plan` `memory/architecture/map.md` `memory/architecture/inventory.md` `.cursor/mcp/serena.md` | `sessions/task-NNN-analysis.md` (draft) + target artifacts named in §plan | — | — |
| **Reviewer** | Reviews implementation against spec and architecture. Returns blocking issues to Implementer. Agrees only when all blockers are resolved. | code in repo `task-NNN.md §spec` `.cursor/memory/architecture/map.md` `.cursor/memory/architecture/checklist.md` | `decisions/task-NNN-review.md` | `skills/code-review.md` `skills/arch-check.md` | `rules/review.md` `rules/cpp.md` `rules/abi.md` |
| **Tester** | Runs build and test suite against test criteria. Reports failures back to Implementer. Agrees only when all criteria pass. | `task-NNN.md §test-criteria` `sessions/task-NNN-impl.md` | `decisions/task-NNN-review.md` (append) | `skills/testing.md` | `rules/testing.md` `rules/determinism.md` |

### Cross-cutting

| Agent | Description | Reads | Writes | Skills | Rules |
|---|---|---|---|---|---|
| **Memory writer** | Persists knowledge from session drafts into permanent project memory. Called as needed at any phase by other agents or the developer. Does not act autonomously. | `sessions/task-NNN-*.md` `decisions/task-NNN-*.md` | `memory/architecture/*` (update) `memory/decisions/adr-log.md` (update) `memory/analysis/*` | `skills/memory-write.md` | `rules/memory.md` |

---

## 5. File structure

```
CLAUDE.md                              # agent entry point — read first, always

.cursor/
  pipeline/
    pipeline.md                        # this document
    loop-design.md                     # rules for the Architect+Planner+Critic loop
    loop-impl.md                       # rules for the Impl+Reviewer+Tester loop

  commands/                              # prompt templates — developer and agent commands
    new-task.md                          # developer: start a new request via Analyst
    review-pr.md                         # developer: code review a pull request
    checkpoint.md                        # developer: show status of active task card(s)
    memory-update.md                     # developer: explicitly trigger Memory writer
    complete-task.md                     # developer: finalize one task after CP5
    complete-request.md                  # developer: finalize request after all its tasks are done
    arch-audit.md                        # developer: full architectural audit of codebase
    arch-map-update.md                   # developer: update map.md to reflect current code
    arch-inventory-sync.md               # developer: sync inventory.md with codebase
    implement-step.md                    # agent: execute one §plan step (TDD order)

  agents/                              # agent role definitions
    analyst.md
    decomposer.md
    architect.md
    planner.md
    critic.md
    spec-writer.md
    test-designer.md
    environment.md
    implementer-cpp.md
    implementer-python.md
    implementer-ml.md
    analyst-code.md
    reviewer.md
    tester.md
    memory-writer.md

  mcp/
    registry.md                        # connected MCP servers: name, purpose, when to use
    serena.md                          # Serena methods, usage patterns, limitations
    <name>.md                          # one file per connected MCP

  skills/                              # HOW to perform a type of task (algorithm)
    dialog.md                          # how to conduct clarifying dialog
    decompose.md                       # how to split a request into task cards
    arch-decision.md                   # how to make and record an arch decision
    planning.md                        # how to produce a step-by-step plan
    critique.md                        # how to attack a plan and find gaps
    spec-writing.md                    # how to write an implementation spec
    test-design.md                     # how to define test scenarios and criteria
    env-setup.md                       # how to prepare build environment
    impl-cpp.md                        # how to implement C++ in this project
    impl-python.md                     # how to implement Python / pybind11
    impl-ml.md                         # how to implement ML components
    dep-analysis.md                    # structural dependency analysis workflow
    pybind.md                          # pybind11 binding patterns
    metrics.md                         # ML metrics and evaluation patterns
    code-review.md                     # how to review code
    arch-check.md                      # how to verify architectural compliance
    testing.md                         # how to run and evaluate tests
    memory-write.md                    # how to distill session drafts into memory

  rules/                               # WHAT is allowed / forbidden per task type
    dialog.md                          # rules for analyst dialog
    decompose.md                       # rules for task decomposition
    arch.md                            # architectural invariants and forbidden patterns
    no-deps-touch.md                   # never modify fetched dependencies
    planning.md                        # planning constraints
    critic.md                          # what Critic must challenge, what it cannot approve
    spec.md                            # spec completeness requirements
    testing.md                         # test coverage and scenario requirements
    determinism.md                     # deterministic AI behavior requirements
    build.md                           # build system rules
    cpp.md                             # C++ coding rules (hot-path, ownership, ABI)
    hotpath.md                         # no alloc, no virtual dispatch, no STL in AI tick
    abi.md                             # ABI stability requirements for public headers
    python.md                          # Python coding rules
    bindings.md                        # pybind11 binding rules
    ml.md                              # ML implementation rules
    review.md                          # review severity levels and blocking criteria
    memory.md                          # what goes into memory, what stays in session

  tasks/
    inbox/                             # raw developer requests (Analyst output)
      request-001.md
      request-002.md
    active/                            # task cards in progress
      task-001-example.md
    sessions/                          # live drafts — readable at any time
      task-001-plan.md
      task-001-impl.md
      task-001-env.md
    decisions/                         # clean final artifacts
      task-001-plan.md
      task-001-review.md
    archive/                           # completed tasks — grouped by request
      request-NNN/                     #   one folder per request (created by complete-task)
        request-NNN.md                 #   request card (moved by complete-request)
        task-NNN-<slug>.md             #   task card(s)
        sessions/                      #   session logs for all tasks in request
        decisions/                     #   decision artifacts for all tasks in request

  memory/
    status.md                          # current state of all memory files — read before accessing memory
    project/
      brief.md                         # what the project is and why
      domain.md                        # domain constraints relevant to the project
      build.md                         # build system facts (presets, toolchain)
    architecture/
      map.md                           # module boundaries, pipelines, invariants
      inventory.md                     # structural reference — all modules and files
      checklist.md                     # enforcement rules with severity levels
      logic/                           # per-module logic descriptions (one file per module)
      analysis/                        # cross-cutting analysis reports (patterns, layering,
                                       # data-flow, performance, reliability, testability,
                                       # tech-debt)
    decisions/
      adr-log.md                       # all architectural decisions with rationale
```

---

## 6. Task card format

Every task card (`tasks/active/task-NNN.md`) is the single file linking all phases for one direction.
Each agent appends its section. The developer sees the full picture in one place.

### Status vocabulary

Every agent that writes to or transitions the task card is required to update `Status:`.
The complete lifecycle with the responsible agent:

| Status value | Set by | When |
|---|---|---|
| `decomposed-awaiting-CP1` | Decomposer | Card written, waiting for developer CP1 approval |
| `decomposed` | Decomposer | Developer has approved CP1 in the same session |
| `architecture-in-progress` | Architect | Architect begins writing §architecture (also set on each §architecture revision during loop) |
| `architecture-ready` | Architect | §architecture written and passed to Planner |
| `planning` | Planner | Planner begins writing plan draft |
| `planned` | Planner | Plan draft written and passed to Critic |
| `design-in-progress` | Critic | Critic begins evaluating the plan (set at start of each iteration) |
| `design-awaiting-CP2` | Critic | Loop stop condition met — plan approved, awaiting developer CP2 |
| `spec-in-progress` | Spec writer | Spec writer begins writing §spec |
| `specified` | Spec writer | §spec draft passed to Test designer |
| `designing-tests` | Test designer | Test designer begins writing §test-criteria |
| `specify-awaiting-CP3` | Test designer | §spec + §test-criteria complete, awaiting developer CP3 |
| `environment` | Environment | Environment agent begins build verification and scaffolding |
| `environment-awaiting-CP4` | Environment | `sessions/task-NNN-env.md` written, awaiting developer CP4 |
| `analysis-in-progress` | Analyst: Code | Analysis begins or resumes (code-analyst tasks only) |
| `analysis-complete` | Analyst: Code | All steps done, artifacts written, ready for developer CP5 (code-analyst tasks only) |
| `impl-in-progress` | Implementer | Implementer begins (or resumes) implementation |
| `implemented` | Implementer | Implementation complete, passed to Reviewer |
| `reviewing` | Reviewer | Reviewer begins evaluation |
| `impl` | Reviewer or Tester | [BLOCKING] issues found — returned to Implementer |
| `reviewed` | Reviewer | Reviewer AGREE, passed to Tester |
| `testing` | Tester | Tester begins running suite |
| `impl-blocked` | Implementer, Reviewer, or Tester | Escalation stops the loop — developer input required |
| `implemented-awaiting-CP5` | Tester | Both Reviewer + Tester AGREE, awaiting developer CP5 |
| `done` | complete-task command | Before archiving files |

```markdown
# Task NNN: <title>
Status: <value from vocabulary above>
Request: request-NNN
Implementer type: cpp | python | ml | code-analyst | tbd

## §request
<what the developer asked — from Analyst dialog>

## §decomposition
<how Decomposer split this from a larger request, if applicable>

## §architecture
<decisions made by Architect — patterns, constraints, affected modules>

## §plan
<approved step-by-step plan from Planner+Critic loop>

## §spec
<implementation specification from Spec writer>

## §test-criteria
<test scenarios, acceptance criteria, metrics from Test designer>

## §status-log
<brief entries: who acted, when, what changed — appended by each agent>
```

---

## 7. Session file format

Session files (`tasks/sessions/task-NNN-*.md`) are live logs.
The developer can read them at any time to see what is happening.

```markdown
# Session: task-NNN <phase>
Started: <timestamp or iteration #>

## Iteration 1
### [AgentName] action
<what the agent did, decided, or wrote>

### [AgentName] response
<feedback or counter-decision>

## Iteration 2
...

## Final — agreed
<summary of what was agreed before writing the clean artifact>
```

---

## 8. Loop stop conditions

### Design loop (Phase 2)
The loop stops when ALL three conditions are met:
- Architect has no unresolved architectural concerns
- Planner has no unresolved planning gaps
- Critic has no remaining [BLOCKING] issues

Loop mechanics, iteration rules, deadlock resolution, and session log format:
see `.cursor/pipeline/loop-design.md`

Output: clean plan written to `tasks/decisions/task-NNN-plan.md`, §plan updated in task card.

### Implementation loop (Phase 5)
The loop stops when ALL two conditions are met:
- Reviewer has no remaining [BLOCKING] issues
- Tester reports all test criteria as PASS

Loop mechanics, iteration rules, escalation to CP2, and session log format:
see `.cursor/pipeline/loop-impl.md`

Output: `decisions/task-NNN-review.md` marked READY, Memory writer called.

---

## 9. Parallel directions

Multiple task cards run the pipeline independently.
- Each card has its own session files and decision files.
- Shared read: `.cursor/memory/**` (read-only for all agents except Architect and Memory writer).
- No cross-task context: an agent working on task-002 does not read task-001 files.
- Memory writer is the only agent that integrates knowledge across tasks.
