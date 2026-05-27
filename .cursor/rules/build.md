# Rules: Build System
# File: .cursor/rules/build.md
# Applied by: Environment, Implementer, Tester

> Build system conventions and rules for this project.
> For build facts (preset names, target names, paths): see memory/project/build.md
>
> [SETUP] Populate memory/project/build.md with actual preset names and targets.
> Update the tables below with project-specific targets if needed.

---

## Project root rule

All build commands must be run from the project root.
Never use `cd` into a subdirectory before running build tools.
Relative paths in build configurations are resolved from the project root.
Running from a subdirectory causes silent path resolution failures.

---

## Build tool rules

Build tool: uv (pure-Python project, no compilation step).

- Manage dependencies through `pyproject.toml` + uv — do not invent ad-hoc environments.
- Use `uv sync` to install; `uv add` to add dependencies. Do not pip-install into the venv directly.
- Never modify `pyproject.toml`/`uv.lock` to work around an issue without developer approval.
- Never modify files fetched by uv (the venv / site-packages) — see `rules/no-deps-touch.md`.

### Standard build sequence

```bash
# From project root — always:
uv sync
uv run ruff check .
uv run pytest
```

---

## Target naming

No compiled targets — pure Python. The package is `llm_agents`; tests live in `tests/`.
See `memory/project/build.md` for authoritative facts.

---

## Impact matrix

When changing a component — which checks must be run and verified:

| Change | package (llm_agents) | tests |
|---|---|---|
| Subsystem implementation | import-check | run affected tests |
| Public `__init__` export | import-check | run dependent tests |
| Dependency change (pyproject) | uv sync | run full suite |

---

## Stub rules

Stubs created by Environment agent must:
- Compile without errors or warnings
- Contain no business logic — marked with `// STUB: task-NNN step N`
- Be added to the correct build target
- Be listed in `sessions/task-NNN-env.md`
- Not be merged — Implementer replaces them during implementation

---

## Verification requirement

Always verify — not assume:
- Build runs without error after stubs are created
- Test runner finds and executes tests
- All bindings can be imported (if applicable)

Document actual command output in `sessions/task-NNN-env.md`.
"Should work" is not a verification result.
