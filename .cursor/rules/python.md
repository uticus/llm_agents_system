# Rules: Python
# File: .cursor/rules/python.md
# Applied by: Implementer: Python, Reviewer

> Primary-language rules for this pure-Python project.

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

- `import llm_agents` (or a subpackage, e.g. `from llm_agents import planning`)
- Import from a subpackage's public surface (its `__init__`), not deep internal modules
- If module import fails — do not proceed, surface to developer

---

## Example rules

- Example scripts are for debugging and integration demonstration
- Integration examples must use real agent/tool usage sequences — do not simplify or reorder calls

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| `from llm_agents import *` | Pollutes namespace, hides what is used |
| Catching bare `except:` | Hides real errors |
| `time.sleep()` in tests | Flaky — use explicit state or mocked clocks |
| Real network calls to LLM providers in unit tests | Slow, flaky, costs tokens — mock the provider boundary |
| Modifying a test to make it pass | Fix the implementation instead |
