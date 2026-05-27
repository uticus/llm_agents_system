# Rules: Python
# File: .cursor/rules/python.md
# Applied by: Implementer: Python, Reviewer

> [SETUP] Update the import module name and test paths to match your project.

---

## Language and style

- Python 3. No Python 2 compatibility code.
- Follow PEP 8 for all Python code
- Type hints recommended for all new functions
- `pytest` is the test runner — all test files named `test_*.py`

---

## Test rules

- Tests follow Given/When/Then structure
- Test function names describe the observable outcome:
  `test_process_returns_result_list` not `test_process`
- No test modifies shared mutable state
- Each test is independent — no ordering dependency

---

## Import rules

<!-- SETUP: Replace <module_name> with the actual importable module name. -->

- `import <module_name>` — always import the full module
- Do not import internal symbols directly
- If module import fails — do not proceed, surface to developer

---

## Example rules

<!-- SETUP: Update the example path to match your project. -->

- Example scripts are for debugging and integration demonstration
- Examples must remain runnable after any binding change
- Integration examples must use real usage sequences — do not simplify or reorder commands

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| Business logic in examples that belongs in C++ | Wrong layer |
| `from <module> import *` | Pollutes namespace, hides what is used |
| Catching bare `except:` | Hides real errors |
| `time.sleep()` in tests | Non-deterministic — use explicit state |
| Modifying test to make it pass | Fix binding or C++ implementation |
