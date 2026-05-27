# Command: implement-step
# File: .cursor/commands/implement-step.md
# Type: agent command
# Used by: Implementer: C++, Implementer: Python, Implementer: ML

> Execute one step from §plan in the correct order:
> dep-analysis → tests → implementation → build → arch-check → log.
> This command orchestrates multiple skills into one standard sequence.

---

## Usage

```
Implement step N of task-NNN
```

## Execution sequence

### 0. Pre-flight

- Verify step N-1 is complete (build passes, tests pass) — or this is step 1
- Read `task-NNN.md §plan step N` — files, what, why, risk, depends-on
- Read `task-NNN.md §spec` entry for step N — interface, contract, constraints
- Read `task-NNN.md §test-criteria` — scenarios relevant to step N

### 1. Dependency analysis (if modifying existing symbol)

Skip if adding a completely new symbol with no existing callers.

Run `skills/dep-analysis.md` for the target symbol.
Capture output. Resolve any VS vs Serena discrepancies before proceeding.

### 2. Verify §spec against architecture

Check `task-NNN.md §spec step N` against `memory/architecture/map.md`:
- New symbol belongs to correct layer
- No new forbidden inter-module dependency
- Hot-path and determinism constraints satisfiable

If conflict found → stop. Flag to developer. Do not implement.

### 3. Write tests (TDD — before implementation)

For each `§test-criteria` scenario relevant to step N:
- Write test code following `skills/impl-cpp.md Phase 2` (or Python/ML equivalent)
- Verify test compiles and **fails** (implementation not yet written)
- Verify test would fail if implementation returns wrong value

### 4. Implement

Follow `skills/impl-cpp.md` (or `impl-python.md` / `impl-ml.md`):
- Implement per `§spec step N` contract
- Replace stub if this symbol was stubbed by Environment
- Add new source files to correct `CMakeLists.txt` if needed

### 5. Build and verify

From project root:
```bash
<build command> --preset <preset> --target <library-target> <test-target>
ctest --preset <preset> --tests-regex <pattern>
```

- Step N tests must pass
- No regression in other tests
- If build fails — fix before proceeding to step N+1

### 6. Architecture self-check

Run `skills/arch-check.md` for changed files:
- Layer assignment correct
- No forbidden dependencies introduced
- Plan-centricity, phase separation, planning backflow — all clear

If any check fails → fix before logging ready.

### 7. Log progress

Append to `sessions/task-NNN-impl.md`:

```markdown
## Iteration {ITER} — [Implementer: {TYPE}]

### Step N: {STEP_TITLE} — DONE
Files changed: <list>
Build: OK
Tests: N pass, M fail
Arch check: PASS
Dep-analysis: ran | skipped (new symbol)
```

---

## Stop conditions

Stop and flag to developer if:
- `§spec step N` is ambiguous — do not interpret
- `§spec step N` conflicts with `memory/architecture/map.md`
- Build cannot be fixed after implementing step N
- `§spec step N` requires modifying external dependency

---

## Notes

- One step per call — do not implement multiple steps in one call
- Do not reorder steps — `§plan` step order is mandatory
- Skills used: `dep-analysis.md`, `impl-cpp.md` / `impl-python.md` / `impl-ml.md`, `arch-check.md`
