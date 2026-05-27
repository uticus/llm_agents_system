# Serena MCP
# File: .cursor/mcp/serena.md

> Structural code analysis server.
> Use Serena for symbol discovery, reference search, and pattern matching in code structure.
> Serena operates on the parsed AST — it understands code structure, not just text.
> For text search (string literals, comments) — use grep instead.

---

## When to use Serena

| Task | Use Serena | Use grep |
|---|---|---|
| Find a symbol definition | yes | no |
| Find all call sites of a function | yes | no |
| Find all references to a class member | yes | no |
| Find pybind11 binding for a symbol | yes | no |
| Find export macros (e.g. MY_API, EXPORT) | yes | no |
| Find a string literal in source | no | yes |
| Find a log message or comment | no | yes |
| Find content in non-code files | no | yes |

---

## Methods

### find_symbol
Finds a symbol definition: function, class, enum, variable, type alias.

```
mcp_serena_find_symbol(
  symbol_name: str,        # exact or partial name
  symbol_type: str,        # "function" | "class" | "enum" | "variable" | "any"
  scope: str               # namespace or class scope, optional
)
```

Returns: qualified name, file path, line number, signature, overloads.

Use for:
- Locating where a symbol is defined
- Collecting all overloads and their signatures
- Finding the header vs source location

---

### find_referencing_symbols
Finds all symbols that reference (call, use, inherit from) a given symbol.

```
mcp_serena_find_referencing_symbols(
  symbol_name: str,        # fully qualified name preferred
  include_indirect: bool   # follow transitive references, default false
)
```

Returns: list of referencing symbols with file, line, and usage context.

Use for:
- Full call-site discovery
- Finding all consumers of a public API
- Cross-checking IDE Find All References results

---

### search_for_pattern
Searches for a structural pattern across the codebase.

```
mcp_serena_search_for_pattern(
  pattern: str,            # pattern string — not regex, structural match
  scope: str               # directory or file scope, optional
)
```

Returns: matches with file, line, and surrounding context.

Use for:
- Finding pybind11 bindings: `PYBIND11_MODULE`, `.def(`, `.def_property`, `enum_`
- Finding export macros: `<YOUR_API_MACRO>` (project-specific)
- Finding specific code patterns not expressible as symbol queries

---

## Usage rules

- Always capture results immediately after each Serena call before running the next.
- Do not dump large result sets into chat — write them to a file in the project root.
- Cross-check Serena results with IDE Find All References for critical refactoring.
- If results are ambiguous or empty — narrow the scope or try a more specific symbol name.
- If Serena and IDE results differ — resolve the discrepancy before proceeding.

---

## Known issues

**Export macros cause incorrect symbol kind**

If public classes are decorated with export macros on the class declaration line, for example:

```cpp
class MY_API MyClass { ... };
```

Due to how Clangd parses macro-expanded declarations, Serena may report these
symbols with `kind: Variable` instead of `kind: Class`. The symbol is still
found correctly — the file path and line number are accurate.

Rules:
- Do NOT filter `find_symbol` results by kind when searching for classes decorated with export macros.
  Use name matching only.
- Do NOT conclude a symbol is missing or misidentified because its kind is `Variable`.
- Verify actual kind by reading the header line if the kind matters for your task.

---

## 5-step dependency analysis workflow

Used by: Implementer: C++, Implementer: Python, Reviewer.
Full algorithm with output capture rules and common patterns:
see `.cursor/skills/dep-analysis.md`

Summary of steps:
1. `find_symbol` — locate definition, collect signatures and overloads
2. IDE Find All References + `find_referencing_symbols` — call-site discovery, cross-check
3. IDE member/field references (READ vs WRITE) + `find_referencing_symbols` — cross-check
4. `search_for_pattern` — bindings (PYBIND11_MODULE, .def(), .def_property, enum_) + export macros
5. `find_referencing_symbols` with `include_indirect: true` — produce complete dependency list

[CRITICAL] Capture output after each step before running the next.
[CRITICAL] If IDE and Serena results differ — resolve before proceeding.
