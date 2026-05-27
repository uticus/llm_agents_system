# Skill: Dependency Analysis
# File: .cursor/skills/dep-analysis.md
# Used by: Implementer: C++, Implementer: Python, Reviewer

> 5-step algorithm for complete dependency analysis before modifying an existing symbol.
> Goal: know every file, call site, and binding that must change before touching anything.
> Always run from project root. Never use `cd` into subdirectories.
>
> [SETUP] Replace the example symbol names and file paths with project-specific examples
> from your codebase after memory files are populated.

---

## Core principle

Do not modify a symbol until you know every place that uses it.
A missed call site means a broken build or a silent regression.
Capture results after each step — do not run all steps and then try to remember.

---

## When to run

Run full 5-step analysis when:
- Modifying an existing function signature
- Renaming a class, method, field, or enum value
- Changing a class member (adding, removing, reordering)
- Moving a symbol to a different file or namespace
- Changing a public header

Skip (use targeted search only) when:
- Adding a completely new symbol with no existing callers
- Modifying a private implementation detail with no header change

---

## Tools

| Tool | When to use |
|---|---|
| Serena MCP | Structural search: symbols, references, patterns |
| IDE Find All References | Call-site discovery — cross-check with Serena |
| Grep | String literals, comments, log messages only |

See `.cursor/mcp/serena.md` for Serena method signatures and usage.

---

## 5-step algorithm

### Step 1: Symbol discovery (Serena)

```
mcp_serena_find_symbol(
  symbol_name: "<target symbol>",
  symbol_type: "function" | "class" | "enum" | "variable" | "any"
)
```

Collect and record:
- Fully qualified name (namespace + class + name)
- Header location (file path + line)
- Source location (file path + line)
- All overloads with their signatures
- Return type and parameter types

**Capture output immediately. Do not proceed until output is recorded.**

If symbol not found or ambiguous — stop. Narrow the search or confirm name with developer.

---

### Step 2: Call-site discovery (IDE + Serena)

**IDE Find All References:**
- Find All References for the target symbol
- Record: file list + surrounding context for each reference
- Separate: definitions vs uses

**Serena cross-check:**
```
mcp_serena_find_referencing_symbols(
  symbol_name: "<fully qualified name from step 1>",
  include_indirect: false
)
```

Compare IDE output and Serena output.
If they differ — resolve the discrepancy before proceeding.
Common causes: template instantiations, macro expansion, forward declarations.

**Capture both outputs. Write to file if large — do not dump into chat.**

---

### Step 3: Member and field access discovery (IDE + Serena)

For each field or member affected by the change:

**IDE Find All References:**
- Find All References for the member
- Separate: READ access vs WRITE access
- Note ownership and lifetime implications

**Serena cross-check:**
```
mcp_serena_find_referencing_symbols(
  symbol_name: "<ClassName::memberName>"
)
```

Record:
- Which code reads this member
- Which code writes this member
- Lifetime implications (who creates, who destroys)

**Capture output. Resolve discrepancies before proceeding.**

---

### Step 4: Pattern search (Serena)

Search for binding-related and export-related patterns:

```
# Python bindings (if applicable)
mcp_serena_search_for_pattern(pattern: "PYBIND11_MODULE")
mcp_serena_search_for_pattern(pattern: ".def(")
mcp_serena_search_for_pattern(pattern: ".def_property")

# Export macros (project-specific)
mcp_serena_search_for_pattern(pattern: "<YOUR_API_MACRO>")
```

Scope to relevant files where possible to reduce noise.

Compare with steps 2-3 outputs.
Any pattern found that was not in steps 2-3 → investigate and add to impact list.

**Capture output after each pattern search.**

---

### Step 5: Final reference check (Serena)

```
mcp_serena_find_referencing_symbols(
  symbol_name: "<fully qualified name>",
  include_indirect: true
)
```

Cross-check against all previous steps.
Produce the complete dependency list:

```
Symbol: <fully qualified name>
Defined in: <header> + <source>
Overloads: <list>

Call sites:
  <file>:<line> — <context>
  ...

Member access:
  READ:  <file>:<line>
  WRITE: <file>:<line>

Binding references:
  <file>:<line> — <binding type>

Export references:
  <file>:<line> — <macro>

Files that must change:
  <public headers>: <list>
  <source files>:   <list>
  <test files>:     <list>
  <binding files>:  <list>
  <example files>:  <list>
```

---

## Output capture rules

- Record output after EACH step — not at the end
- Write large result sets to a file in project root, not into chat
- Do not run step N+1 if step N output is not captured
- If IDE and Serena results differ — resolve before proceeding

---

## Stop conditions

Stop the analysis and escalate to developer if:
- Symbol cannot be found in step 1 (name may be wrong)
- IDE and Serena results differ and cannot be reconciled
- Binding search reveals unexpected references (undocumented API surface)
- Impact list grows beyond the scope defined in §decomposition
