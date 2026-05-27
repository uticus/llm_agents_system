# Command: setup-project
# File: .cursor/commands/setup-project.md
# Used by: Developer (initial project setup) or an agent triggered by the developer

> This command runs once, when the agents pipeline is first used in a new project.
> Purpose: fill in all project-specific placeholders so the pipeline is ready to use.
> The agent executing this command acts as a specialized setup agent, not as Analyst or any pipeline role.

---

## When to run

Run this command exactly once, after copying the agents pipeline folder into a new project.
Do not run on an already-configured project — it will overwrite existing configuration.

Trigger:
```
Read SETUP.md, then read .cursor/commands/setup-project.md and execute it.
```

---

## What this command does

This command collects project information through a structured dialog with the developer,
then fills in all `[SETUP]` placeholders across the pipeline files.

It does NOT:
- Create source code
- Make architectural decisions
- Run builds or tests
- Activate any pipeline agent

---

## Algorithm

### Step 1: Read current state

Read these files to understand what is already filled in vs what still has `[SETUP]` markers:
- `SETUP.md`
- `CLAUDE.md`
- `.mcp.json`
- `.serena/project.yml`
- `.cursor/memory/project/brief.md`
- `.cursor/memory/project/domain.md`

Note which fields already contain real content vs placeholders.

---

### Step 2: Collect project information through dialog

Ask the developer the following questions. Ask 2-3 per message maximum.
Wait for answers before proceeding.

**Block A: Project identity (required)**

1. What is the project name? (short, no spaces, e.g. `my_project`)
2. What does the project do? (one sentence)
3. What is the primary programming language? (e.g. C++20, Python, TypeScript, Go)
4. Does the project have Python bindings (pybind11)? (yes / no)
5. Does the project have ML components requiring inference? (yes / no)
6. What is the build system? (CMake, npm/webpack, cargo, make, other)
7. What is the toolchain? (Visual Studio, GCC, Clang, etc.)

**Block B: Build configuration (required for Environment agent)**

8. What is the primary library target name? (e.g. `mylib`, the output .dll/.so/.a)
9. What is the test target name? (e.g. `mylib_tests`)
10. What preset or configuration name is used for building? (e.g. `win-vs2022-x64-tests` or `debug`)
11. What is the test runner command? (e.g. `ctest`, `pytest`, `cargo test`, `npm test`)

**Block C: API surface (required for ABI and binding rules)**

12. What are the public header files / stable interface files? (list paths)
13. What is the primary entry point class or function? (e.g. factory pattern, main function, module)

**Block D: MCP configuration (required for memory-palace and Serena)**

14. What is the path to your Python executable? (e.g. `C:\Python\Python312\python.exe`)
15. Where is memory-palace installed? (the directory containing `mcp_server/`)
16. Where should memory-palace store data? (e.g. `C:\Users\<name>\.memory-palace`)
17. What is the absolute path to this project root? (e.g. `d:\Work\MyProject\repo`)

**Block E: Domain constraints (optional but recommended)**

18. Does the system require deterministic behavior? (same input → same output) (yes / no)
19. Are there performance-critical tight loops that must not allocate? (yes / no)
20. What is the primary domain? (e.g. game AI, web backend, data pipeline, embedded, CLI tool)
21. What does the system explicitly NOT do? (list 2-3 out-of-scope items)

**Block F: Language-specific**

If Python bindings (from question 4):
22. What is the Python module name? (e.g. `import mymodule`)
23. Where is the bindings source file? (e.g. `bindings/src/bindings.cpp`)

---

### Step 3: Confirm before writing

Present a summary:

```
Project setup summary:

Name: [PROJECT_NAME]
Description: [one sentence]
Language: [language]
Build: [build tool] — targets: [lib-target], [test-target]
Preset: [preset name]
Test runner: [command]
Public API: [header paths]
Python bindings: yes/no — module: [name if yes]
Determinism required: yes/no
Hot paths exist: yes/no
Memory palace: [path config]
Serena project root: [path]

Is this correct?
```

Wait for explicit confirmation before writing any files.

---

### Step 4: Write configuration files

Write in this order. After each file, verify it was written correctly.

**4.1 CLAUDE.md** — update the project identity table:
- Replace `[PROJECT_NAME]`, `[one-sentence description]`
- Fill in: Primary language, Bindings, Build, Toolchain

**4.2 .mcp.json** — replace all `SETUP_*` values:
- `SETUP_PYTHON_PATH` → answer to Q14
- `SETUP_MEMORY_PALACE_DIR` → answer to Q15
- `SETUP_MEMORY_PALACE_DATA_DIR` → answer to Q16
- `SETUP_PROJECT_ROOT` → answer to Q17

**4.3 .serena/project.yml** — update:
- `project_name` → answer to Q1 (lowercase, no spaces)
- `languages` → set to primary language(s) from Q3

**4.4 .serena/memories/project_overview.md** — write a 3-5 sentence description:
- Purpose sentence from Q2
- Tech stack from Q3, Q6, Q7
- Key modules from Q12 and Q13
- Test framework from Q11

**4.5 .serena/memories/suggested_commands.md** — fill in:
- Configure command with preset from Q10
- Build commands with target names from Q8 and Q9
- Test runner command from Q11
- Python import command if bindings (Q4, Q22)

**4.6 .cursor/memory/project/brief.md** — fill in all sections:
- Project name and description (Q1, Q2)
- Public API entry points (Q12, Q13)
- Language table (Q3)
- Key constraints (Q18 → determinism, Q19 → performance)
- Out-of-scope items (Q21)

**4.7 .cursor/memory/project/domain.md** — fill in:
- Domain type (Q20)
- Determinism requirement (Q18)
- Performance constraints (Q19)
- Leave edge cases section for developer to fill or leave as template

**4.8 .cursor/memory/project/build.md** — fill in:
- Build system (Q6)
- Target names (Q8, Q9)
- Preset name (Q10)
- Build and test commands (Q11)

**4.9 .cursor/rules/build.md** — update target table with Q8, Q9 values

**4.10 .cursor/rules/python.md** — if Python bindings (Q4):
- Replace `<module_name>` with Q22

**4.11 .cursor/rules/hotpath.md** — if no hot paths (Q19 = no):
- Add a note at the top: "Hot-path rules not applicable to this project."

**4.12 .cursor/rules/determinism.md** — if no determinism requirement (Q18 = no):
- Add a note at the top: "Determinism rules not applicable to this project."

**4.13 Remove unused files** — based on answers:
- Q4 = no → move to a `_unused/` folder or delete: `rules/bindings.md`, `rules/python.md`,
  `skills/pybind.md`, `skills/impl-python.md`, `agents/implementer-python.md`
- Q5 = no → move or delete: `rules/ml.md`, `skills/impl-ml.md`, `skills/metrics.md`,
  `agents/implementer-ml.md`

---

### Step 5: Update memory status

Write `.cursor/memory/status.md` — update the "not yet created" entries for the files
that were just populated (brief.md, domain.md, build.md now have status "created").

---

### Step 6: Confirm completion

Output:

```
Setup complete.

Files written:
- CLAUDE.md (updated)
- .mcp.json (configured)
- .serena/project.yml (configured)
- .serena/memories/project_overview.md (written)
- .serena/memories/suggested_commands.md (written)
- .cursor/memory/project/brief.md (populated)
- .cursor/memory/project/domain.md (populated)
- .cursor/memory/project/build.md (populated)
- .cursor/memory/status.md (updated)
- .cursor/rules/build.md (updated)
[additional files based on choices]

Files that still need manual attention:
- .cursor/memory/architecture/map.md — will be filled by Architect on first design task
- .cursor/memory/architecture/inventory.md — will be filled by Analyst: Code
- .cursor/memory/architecture/checklist.md — will be filled by Architect
- .cursor/memory/decisions/adr-log.md — will be created by Memory writer on first ADR

The pipeline is ready. To start your first request:
  @agent:analyst — [describe your request]
```

---

## Notes

- This command does not run any builds or tests.
- The files it creates are used by all subsequent pipeline agents.
- If any answer changes later — re-run the specific file update, or ask Memory writer to update.
- If memory-palace is not available, remove `memory-palace` from `.cursor/mcp/registry.md`.
