# Rules: Python Bindings
# File: .cursor/rules/bindings.md
# Applied by: Implementer: Python, Reviewer, Architect

> Rules for pybind11 bindings.
> Bindings are part of the public API — same stability standards as C++ headers.
>
> [SETUP] Update file path reference in the Layer boundary rule to match your project.
> Remove this file if your project does not use Python bindings.

---

## Layer boundary rule

Bindings must be a thin translation layer only.
No business logic, no control flow, no state in bindings source.

Allowed in bindings:
- `.def()`, `.def_property()`, `.def_static()`
- `py::class_<>`, `py::enum_<>`
- `py::register_exception<>`
- Lambda wrappers for type conversion only (no logic)

Forbidden in bindings:
- `if` / `else` based on domain state
- Loops over domain objects
- Calls to business logic
- Any state that persists between Python calls

---

## Stability rules

- Bindings are public API — same ABI stability rules as public headers
- Adding new bindings is safe (additive)
- Removing or renaming existing bindings is breaking — requires ADR
- Changing `py::arg()` names is breaking for keyword callers — treat as breaking
- See `rules/abi.md` for complete ABI rules

---

## Ownership rules

- Every bound class must specify ownership model explicitly
- `shared_ptr<T>` — use `py::class_<T, shared_ptr<T>>`
- Raw owning pointer — forbidden
- Non-owning reference — use `py::return_value_policy::reference_internal`
  and document lifetime dependency in docstring

---

## Exception rules

- Every C++ exception reachable from a binding must be mapped
- Unmapped C++ exceptions produce opaque `SystemError` in Python
- Use `py::register_exception<>` or `py::register_exception_translator`
- Exception mapping must be registered before any binding that can throw

---

## Docstring requirement

Every exposed symbol must have a docstring:
- Classes: describe purpose and ownership
- Methods: describe parameters, return value, exceptions
- Enums: describe each value
- Use `R"(...)"` raw string literals for multi-line docstrings

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| Business logic in `.def()` lambda | Belongs in C++ |
| Raw owning `T*` in binding | Undefined lifetime from Python |
| Missing exception mapping | Opaque SystemError in Python |
| No docstring | Python users have no documentation |
| Binding internal (non-public) C++ symbol | Bypasses API boundary |
| `export_values()` on all enums | Pollutes module namespace — use only when needed |
