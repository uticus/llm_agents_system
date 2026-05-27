# Skill: Python Binding Implementation
# File: .cursor/skills/impl-python.md
# Used by: Implementer: Python

> Algorithm for implementing pybind11 binding changes.
> Goal: thin, correct, stable binding layer with no business logic.
>
> [SETUP] Replace placeholder paths and module names with the actual values for this project.
> See memory/project/build.md for binding source file path and module name.

---

## Core principle

Bindings are a translation layer — not an implementation layer.
Every line in the bindings source should be a `.def()`, `.def_property()`, or `py::class_<>`.
If you find yourself writing an `if` or a loop in the bindings — stop.
That logic belongs in C++.

---

## Algorithm

### Phase 1: Audit existing binding surface

Before adding or changing any binding, read the full bindings source file.
Map what is currently exposed:

```
Module: <PYBIND11_MODULE name>
Classes: [list]
Functions: [list]
Enums: [list]
Properties: [list]
```

This prevents duplicate bindings and naming conflicts.

### Phase 2: Verify C++ side is ready

For each symbol to bind:
```bash
# Verify symbol exists and is in the public header
grep -r "<SymbolName>" <public-include-dir>/
```

If symbol is not in the public header — it is not part of the public API.
Do not bind internal symbols. Flag to Architect if §spec requires it.

### Phase 3: Implement bindings

**Binding a free function:**
```cpp
m.def("python_name",
    &CppNamespace::FunctionName,
    py::arg("param1"), py::arg("param2") = default_value,
    R"(Docstring from §spec.)");
```

**Binding a class:**
```cpp
py::class_<ClassName, std::shared_ptr<ClassName>>(m, "ClassName",
    R"(Class docstring from §spec.)")
    .def(py::init<ConstructorParamType>(),
         py::arg("param"),
         R"(Constructor docstring.)")
    .def("method_name",
         &ClassName::MethodName,
         py::arg("param"),
         R"(Method docstring.)")
    .def_property_readonly("property_name",
         &ClassName::GetProperty,
         R"(Property docstring.)");
```

**Ownership rules:**
```cpp
// Shared ownership (most common):
py::class_<ClassName, std::shared_ptr<ClassName>>(m, "ClassName")

// Factory function returning unique_ptr — transfer ownership:
m.def("create", []() { return std::make_unique<ClassName>(); })
// pybind11 handles unique_ptr → Python object ownership transfer

// Non-owning reference — use reference_internal:
.def_property_readonly("child",
    &Parent::GetChild,
    py::return_value_policy::reference_internal,
    R"(Non-owning reference to child — lifetime tied to parent.)")
```

### Phase 4: Exception mapping

For each new C++ class or function that can throw:

```cpp
// Register before the binding that can throw:
py::register_exception<ProjectSpecificError>(m, "ProjectError");
```

Verify all exceptions in the binding surface are mapped.
See `skills/pybind.md` for patterns.

### Phase 5: Build and verify

```bash
# From project root
<build command> --preset <preset> --target <bindings-target>

# Verify import
python -c "import <module_name>; print('ok')"

# Verify exposed symbols
python -c "import <module_name>; print(dir(<module_name>))"
```

Both commands must succeed before proceeding.

### Phase 6: Write tests

```python
import <module_name>

def test_<class_name>_<method_name>():
    # Given
    obj = <module_name>.ClassName(param)

    # When
    result = obj.method_name(arg)

    # Then
    assert isinstance(result, <module_name>.ExpectedType)
    assert result.property == expected_value
```

Tests must verify:
- Object can be constructed from Python
- All bound methods return the correct Python type
- Exceptions propagate as the correct Python exception type

### Phase 7: Run tests

```bash
pytest <test-path>/test_task_NNN.py -v --tb=short
```

Record each failure with file, line, expected, actual.

---

## Build troubleshooting

| Symptom | Action |
|---|---|
| `ImportError` | Check build succeeded and output `.pyd`/`.so` is on the Python path |
| `AttributeError: module has no attribute X` | Binding for X was not added or not compiled |
| `TypeError: method takes N arguments` | Argument count mismatch — check `.def()` signature |
| `SystemError` | Unmapped C++ exception — add `py::register_exception<>` |
| Segfault | Lifetime issue — check `return_value_policy` |
