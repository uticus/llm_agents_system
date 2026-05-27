# Skill: pybind11 Patterns
# File: .cursor/skills/pybind.md
# Used by: Implementer: Python, Reviewer

> Reference for pybind11 patterns used in this project.
> Goal: consistent, correct binding patterns across the codebase.
>
> [SETUP] Remove this file if the project does not use pybind11.
> Update the enum example values to use actual project types.

---

## Ownership patterns

| C++ ownership | pybind11 pattern | When to use |
|---|---|---|
| `shared_ptr<T>` | `py::class_<T, shared_ptr<T>>` | Objects with shared lifetime |
| `unique_ptr<T>` return | Normal `.def()` — pybind11 transfers | Factory functions |
| Non-owning `T*` or `T&` | `py::return_value_policy::reference_internal` | Accessors returning refs to members |
| `const T&` return | `py::return_value_policy::copy` | Small value types |

Never bind a raw owning pointer — ownership is undefined from Python side.

---

## Argument handling

```cpp
// Required argument
.def("method", &Class::Method, py::arg("name"))

// Optional with default
.def("method", &Class::Method, py::arg("name") = default_value)

// Keyword-only (after py::kw_only())
.def("method", &Class::Method, py::kw_only(), py::arg("name"))

// Pass by reference (avoid copy for large objects)
.def("method", &Class::Method, py::arg("obj").noconvert())
```

---

## Overload resolution

```cpp
// Explicit overload selection
.def("method",
    py::overload_cast<int>(&Class::Method),
    py::arg("int_param"))
.def("method",
    py::overload_cast<const std::string&>(&Class::Method),
    py::arg("str_param"))

// Const overload
.def("get_value",
    py::overload_cast<>(&Class::GetValue, py::const_))
```

---

## Properties

```cpp
// Read-only
.def_property_readonly("name", &Class::GetName)

// Read-write
.def_property("value",
    &Class::GetValue,
    &Class::SetValue)

// Static read-only
.def_property_readonly_static("constant",
    [](py::object) { return Class::kConstant; })
```

---

## Exception mapping

Map every C++ exception that can reach the binding surface:

```cpp
// In PYBIND11_MODULE, before other bindings:
py::register_exception<std::invalid_argument>(m, "InvalidArgumentError");
py::register_exception<std::runtime_error>(m, "RuntimeError");

// Custom exception with message forwarding:
py::register_exception_translator([](std::exception_ptr p) {
    try {
        if (p) std::rethrow_exception(p);
    } catch (const CustomException& e) {
        PyErr_SetString(PyExc_ValueError, e.what());
    }
});
```

Never let a C++ exception propagate to Python uncaught —
it produces an opaque `SystemError` with no useful message.

---

## Enum binding

```cpp
// SETUP: Replace Phase values with actual project enum values
py::enum_<Phase>(m, "Phase")
    .value("VALUE_A",  Phase::ValueA,  "Description A")
    .value("VALUE_B",  Phase::ValueB,  "Description B")
    .export_values();  // omit if enum values should not pollute module namespace
```

Enum value order in binding must match C++ declaration order — do not reorder.

---

## Docstrings

Every exposed symbol must have a docstring. Format:

```cpp
.def("method_name",
    &Class::MethodName,
    py::arg("param"),
    R"(
    Brief description from §spec.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.
    )")
```

Use raw string literals `R"(...)"` for multi-line docstrings.
Single-line docstrings can use plain string literal.

---

## ABI stability in bindings

Adding to bindings is safe (additive). Removing or changing breaks Python callers.

| Change | ABI impact |
|---|---|
| Add new `.def()` | Safe — new symbol |
| Add optional argument with default | Safe — existing calls still work |
| Remove `.def()` | Breaking — Python callers get AttributeError |
| Change argument name in `py::arg()` | Breaking — keyword callers break |
| Change return type | Breaking — Python code may fail at runtime |
| Add required argument | Breaking — existing calls fail |

See `rules/abi.md` for full ABI rules.
