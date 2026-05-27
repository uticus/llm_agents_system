# Rules: C++ Coding
# File: .cursor/rules/cpp.md
# Applied by: Implementer: C++, Reviewer

> C++ coding rules for this project. Applied to all new and modified code.
>
> [SETUP] This file contains sensible defaults for C++20 projects.
> Adjust naming conventions and error handling to match your codebase.

---

## Language standard

C++20. Use modern C++ features where they improve clarity and safety.
Do not use deprecated features. Do not use compiler extensions.

---

## Include guards

`#pragma once` is the only accepted include guard form.
Traditional `#ifndef` guards are forbidden in new code.

---

## Naming conventions

Follow the existing convention in each module. Before writing new code,
read 2-3 existing files in the same module to establish the pattern.

<!-- SETUP: Fill in the actual naming conventions observed in your codebase. -->
General conventions to verify from existing code:
- Classes: (read existing files to determine convention)
- Member fields: (read existing files to determine convention)
- Methods: (read existing files to determine convention)
- Local variables: (read existing files to determine convention)
- Constants: (read existing files to determine convention)

---

## Ownership rules

- No raw owning pointers (`T*` where T is owned) in new code
- Use `std::unique_ptr<T>` for exclusive ownership
- Use `std::shared_ptr<T>` for shared ownership
- Use `const T&` or `T*` for non-owning references — add comment `// non-owning`
- No `delete` in application code — ownership handled by smart pointers / RAII
- Destructors must not throw

---

## Const-correctness

- Methods that do not mutate object state must be `const`
- Parameters passed by reference that are not modified must be `const T&`
- `mutable` is allowed only for cache fields — must be documented with comment

---

## Error handling

Follow the existing pattern in the module being modified.
Do not introduce a new error handling style without architectural approval.

Common patterns to check in existing code:
- `assert()` for programmer errors (precondition violations, impossible states)
- Return value / out-parameter for recoverable errors
- Exceptions policy (check `memory/architecture/map.md` for project stance)

---

## Documentation

Every new public function must have a `/// @brief` comment.
Internal functions: comment if the intent is not obvious from the name.
No commented-out code in committed files.

---

## Magic numbers

No magic numbers in new code. Use named constants.
```cpp
// Wrong
if (count > 18) { ... }

// Correct
constexpr int kMaxCount = 18;
if (count > kMaxCount) { ... }
```

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| Raw owning `T*` | Use smart pointers |
| `const_cast` without documented justification | Hides design problems |
| `reinterpret_cast` in public API | ABI and safety risk |
| Magic numbers | Use named constants |
| `#ifndef` include guards | Use `#pragma once` |
| `using namespace std` in headers | Pollutes caller namespace |
| Signed integer overflow | Undefined behavior |
| Out-of-bounds access | Undefined behavior |
