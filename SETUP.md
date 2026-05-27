# SETUP.md
# Agents Pipeline — New Project Setup Guide

> Read this when using this folder in a new project.
> Do not modify this file after setup is complete — it is a guide, not a configuration file.
> Language: English only. No emojis.

---

## What this folder is

This is the `.cursor/` agents pipeline — a reusable multi-agent workflow for software
development using Cursor + Claude. It provides:

- A structured pipeline from request → design → implementation → review
- Role-specific agent definitions with precise read/write contracts
- A memory system that persists knowledge across sessions
- Reusable skills and rules for common task types (C++, Python, ML, analysis)

---

## How to use this in a new project

### Step 1: Copy the folder

Copy the entire `agents_pipeline/` folder content into the root of your project.
The folder structure must be preserved:

```
<your-project-root>/
  CLAUDE.md
  SETUP.md                  ← this file
  .cursorrules
  .mcp.json
  .gitignore
  .cursor/
    agents/
    pipeline/
    mcp/
    skills/
    rules/
    memory/
    tasks/
    commands/
  .serena/
```

### Step 2: Run the setup agent

Open Cursor in your project root.
Start a new chat with this prompt:

```
Read SETUP.md, then read .cursor/commands/setup-project.md and execute it.
```

The setup agent will ask you questions and fill in all project-specific content.

Alternatively — fill in the placeholders manually following Step 3 below.

---

## Step 3: Manual setup (if not using the setup agent)

Work through the files that contain `[SETUP]` markers. The complete list:

### 3.1 CLAUDE.md

Fill in the project identity table:
```
[PROJECT_NAME] — your project's name
Primary language — C++20, Python, TypeScript, etc.
Bindings — if applicable
Build — CMake, npm, cargo, etc.
Toolchain — VS, GCC, Clang, etc.
```

### 3.2 .mcp.json

Replace all `SETUP_*` placeholders:
- `SETUP_PYTHON_PATH` → path to `python.exe` (e.g. `C:\Python\Python312\python.exe`)
- `SETUP_MEMORY_PALACE_DIR` → path to memory-palace installation directory
- `SETUP_MEMORY_PALACE_DATA_DIR` → path to memory palace data directory (e.g. `C:\Users\<name>\.memory-palace`)
- `SETUP_PROJECT_ROOT` → absolute path to your project root (e.g. `d:\Work\MyProject\repo`)

### 3.3 .serena/project.yml

- `project_name` → your project name (no spaces, lowercase)
- `languages` → set to the primary language(s) used: `cpp`, `python`, `typescript`, etc.

### 3.4 .serena/memories/project_overview.md

Replace with a 3-5 sentence description of the project.
Include: purpose, primary tech stack, key modules, test framework.

### 3.5 .serena/memories/suggested_commands.md

Replace with the actual build, test, and import commands for this project.

### 3.6 .cursor/memory/project/brief.md

Fill in:
- Project name and one-sentence description
- Public API entry points and stable interfaces
- Supported use cases
- Language table
- Key constraints (determinism, performance, threading, ownership)
- What the project does NOT do (explicit out-of-scope list)
- Project structure (key paths)
- Integration test rule

### 3.7 .cursor/memory/project/domain.md

Fill in:
- Domain characteristics relevant to code structure
- Primary system objective
- Input and output structure
- Scale and performance constraints
- Determinism requirements (or remove section)
- Domain-specific edge cases that affect test design

### 3.8 .cursor/rules/arch.md

Fill in the `[SETUP]` sections:
- Hot-path entry points and the forbidden patterns for them
- Keep or remove the determinism section

### 3.9 .cursor/rules/build.md

Fill in:
- Build tool name and commands
- Target table with actual target names
- Impact matrix

### 3.10 .cursor/rules/cpp.md

Fill in the naming conventions section with the actual conventions observed in the codebase.

### 3.11 .cursor/rules/python.md

Replace `<module_name>` with the actual importable module name.

### 3.12 .cursor/skills/planning.md

Fill in the risk assessment section with actual hot paths and binding file paths.

### 3.13 .cursor/skills/arch-check.md

Fill in the layer definitions from `memory/architecture/map.md` once that is populated.

### 3.14 .cursor/skills/impl-cpp.md and env-setup.md and testing.md

Replace `<preset>`, `<library-target>`, `<test-target>` with actual names
from `memory/project/build.md`.

---

## Step 4: Remove unused components

If your project does not use Python bindings — remove or clearly mark as unused:
- `.cursor/rules/bindings.md`
- `.cursor/rules/python.md`
- `.cursor/skills/pybind.md`
- `.cursor/skills/impl-python.md`
- `.cursor/agents/implementer-python.md`

If your project does not have performance-critical hot paths — remove or mark:
- `.cursor/rules/hotpath.md`

If your project does not require deterministic behavior — remove or mark:
- `.cursor/rules/determinism.md`

If your project does not have ML components — remove or mark:
- `.cursor/rules/ml.md`
- `.cursor/skills/impl-ml.md`
- `.cursor/skills/metrics.md`
- `.cursor/agents/implementer-ml.md`

---

## Step 5: First use

Once setup is complete:

1. Start a request with the Analyst agent:
   ```
   @agent:analyst — [describe your request]
   ```

2. The pipeline proceeds: Analyst → Decomposer → Architect → Planner → Critic → Spec writer
   → Test designer → Environment → Implementer → Reviewer → Tester

3. Developer checkpoints (CP1–CP5) are the points where you review and approve.

---

## Step 6: Memory palace setup (optional but recommended)

The memory palace provides semantic recall across sessions. To set it up:

1. Install memory-palace: follow instructions at https://github.com/jeffpierce/memory-palace
2. Configure `.mcp.json` with the correct paths (Step 3.2 above)
3. On first task completion, Memory writer will begin populating the palace

If memory-palace is not available, agents fall back to reading markdown files directly.
Remove `memory-palace` from `.cursor/mcp/registry.md` if not using it.

---

## Files to verify before first use

Run through this checklist:

- [ ] `CLAUDE.md` — project identity table filled in
- [ ] `.mcp.json` — no `SETUP_*` placeholders remain
- [ ] `.serena/project.yml` — `project_name` and `languages` set
- [ ] `.serena/memories/project_overview.md` — describes actual project
- [ ] `.serena/memories/suggested_commands.md` — actual build/test commands
- [ ] `.cursor/memory/project/brief.md` — filled in (or will be filled by setup agent)
- [ ] `.cursor/memory/project/domain.md` — filled in (or will be filled by setup agent)
- [ ] `.cursor/memory/status.md` — reflects actual state (all "not yet created" is fine initially)
