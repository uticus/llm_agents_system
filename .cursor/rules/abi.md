# Rules: ABI Stability
# File: .cursor/rules/abi.md
# Applied by: Implementer: C++, Reviewer, Architect

> ABI stability rules for public headers.
> Violations require explicit developer approval and an ADR.
>
> [SETUP] Replace the public API boundary section with actual file paths for your project.

---

## Public API boundary

<!-- SETUP: List the actual public header files for your project. -->

Files defining the stable ABI:
- `<your-project>/include/<main-header>.h` — primary interface
- `<your-project>/include/<api-def>.h` — export macros

Any change to these files has ABI implications.

---

## ABI-safe changes (additive)

| Change | Notes |
|---|---|
| Add new non-virtual method | Safe — does not change vtable or layout |
| Add new overload | Safe — new symbol, existing callers unaffected |
| Add new class | Safe — new symbol |
| Add enum value at end | Safe — existing values unchanged |
| Add default argument | Safe for source, callers must recompile |

---

## ABI-breaking changes

Require developer approval + ADR:

| Change | Why breaking |
|---|---|
| Change function signature | Callers compiled against old signature break |
| Remove or rename function | Missing symbol at link time |
| Add virtual method | Changes vtable layout |
| Reorder virtual methods | Changes vtable offsets |
| Add non-static data member to class | Changes object layout and size |
| Reorder or remove enum value | Changes integer values |
| Change base class | Changes object layout |

---

## Assessment requirement

Every change to a public header must include an ABI impact assessment in §spec:
- Additive: safe, no action needed beyond recompile
- Breaking: developer approval required, ADR required, migration path documented

---

## Binding impact

Any change to a public header affecting the binding surface requires:
- Update to the binding layer (e.g. `bindings.cpp` for pybind11)
- Verify: bindings build and can be imported
- Handled by Implementer: Python — flag it, do not implement it yourself
