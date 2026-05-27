# Agents Pipeline (Template)

This repository folder is a **project-agnostic multi-agent workflow template** for using Cursor agents with a file-based handoff pipeline:

**request → decomposition → design (loop) → spec → tests → environment → implementation (loop) → review → testing**

The template is intended to be **copied into other repositories** and configured there.

---

## Quick start (new project)

1. Copy the contents of this folder into your repo root (preserve structure).
2. In Cursor, run the setup command:

```
Read SETUP.md, then read .cursor/commands/setup-project.md and execute it.
```

This fills in all `[SETUP]` placeholders (project name, build system, targets, paths, etc.).

---

## Where to look

- **Setup guide**: `SETUP.md`
- **Setup command**: `.cursor/commands/setup-project.md`
- **Entry point for agents**: `CLAUDE.md`
- **Pipeline definition**: `.cursor/pipeline/pipeline.md`
- **MCP registry**: `.cursor/mcp/registry.md`
- **Memory status**: `.cursor/memory/status.md`
- **Task template**: `.cursor/tasks/task-template.md`

---

## Notes

- All content is **English-only** and uses markers: `[CRITICAL] [WARNING] [OK] [ERROR] [BLOCKING]`.
- The template supports optional layers (Python bindings, ML, determinism, hot paths). Remove unused parts after setup if desired.

