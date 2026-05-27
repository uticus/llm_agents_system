# Skill: Test Execution
# File: .cursor/skills/testing.md
# Used by: Tester

> Algorithm for running the test suite and evaluating results against §test-criteria.
> Goal: precise, complete, reproducible test execution with actionable failure reports.
>
> [SETUP] Replace placeholder commands with actual test runner commands for your project.
> See memory/project/build.md for authoritative preset names and target names.

---

## Core principle

Run everything. Report precisely.
A filtered test run that misses a regression is worse than no test run.
A vague failure message that Implementer cannot act on wastes an iteration.

---

## Algorithm

### Phase 1: Pre-flight checks

Before running any test:

1. Verify Reviewer AGREE exists in `sessions/task-NNN-impl.md`
   — do not test before Reviewer approval
2. Verify build succeeds for all affected targets
3. Note any Reviewer [WARNING] items that may affect test execution

```bash
# From project root — always
<build command> --preset <preset> --target <library-target>
<build command> --preset <preset> --target <test-target>
```

If build fails → stop. Report [BLOCKING] to Implementer. Do not proceed.

### Phase 2: Run full test suite

```bash
<test runner> --preset <preset>
```

**Never filter the run** — run all tests every time.
Use name filters only to investigate specific failures after the full run.

Record:
```
Total:   N tests
Passed:  N
Failed:  M  (list each)
Skipped: K  (list each — should be 0 for new tests)
```

### Phase 3: Map results to §test-criteria

For each scenario in §test-criteria:
1. Find the corresponding test by name
2. Verify it ran (not skipped)
3. Verify it passed

Build coverage table:
```
| Scenario | Test name | Ran? | Result |
|---|---|---|---|
| S01 | SuiteName.ScenarioName | yes | PASS |
| S02 | SuiteName.OtherName | yes | FAIL |
| S03 | — | no | MISSING |
```

MISSING = [BLOCKING]. Implementer must write the test.
SKIPPED = [BLOCKING]. Investigate why — test should not be skipped.

### Phase 4: Regression check

Compare against expected baseline (all tests passing before this task):
- Any previously passing test now failing = REGRESSION = [BLOCKING]
- Flag: "REGRESSION: TestName was passing before task-NNN"

### Phase 5: Determinism verification

For each determinism scenario in §test-criteria:

```bash
# Run 1
<test runner> --filter=<determinism_test> > run1.txt

# Run 2 — same binary, same seed
<test runner> --filter=<determinism_test> > run2.txt

# Run 3
<test runner> --filter=<determinism_test> > run3.txt

# Compare
diff run1.txt run2.txt
diff run1.txt run3.txt
```

If any diff is non-empty → [BLOCKING] determinism violation.
Report: which run differed, at which line, what the exact difference was.

### Phase 6: Python test execution (if applicable)

```bash
# Verify import first
python -c "import <module_name>; print('ok')"

# Run tests
pytest test_task_NNN.py -v --tb=short
```

Record each failure:
```
FAILED test_task_NNN.py::test_function_name
  AssertionError: assert <actual> == <expected>
  <traceback>
```

### Phase 7: Write results

Append to `sessions/task-NNN-impl.md`.

If AGREE: also write Tester section to `decisions/task-NNN-review.md`.

---

## Failure report format

Every failure report must contain:
- Test name (exact, copy-paste ready)
- File path and line number
- Expected value
- Actual value
- Failure message (exact, from test output)

Vague report: "test_new_class failed"
Actionable report:
```
[BLOCKING] NewClass.returns_empty_when_no_targets (tests/test_new_class.cpp:42)
  Expected: result.empty() == true
  Actual:   result.size() == 1
  Message:  Value of: result.empty()
            Actual: false
            Expected: true
```

---

## Re-run rules

After Implementer fixes an issue — always re-run the full suite.
Never run only the previously failing test — regressions hide in adjacent tests.

If the same test fails 3 times after 3 fix attempts → surface deadlock to developer.
