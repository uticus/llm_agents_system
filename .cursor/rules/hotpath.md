# Rules: Hot Path
# File: .cursor/rules/hotpath.md
# Applied by: Implementer: C++, Reviewer, Architect

> Performance constraints for tight loops and time-critical code paths. Violations are [ERROR].
>
> [SETUP] Replace the hot-path entry point examples with your project's actual hot paths.
> See memory/architecture/map.md for the authoritative list.

---

## What is a hot path

<!-- SETUP: List the actual hot-path entry points for your project. -->
<!-- Example structure: -->

Hot paths in this project — called on every processing cycle or in tight loops:
- `<ModuleName>::<MethodName>()` and all functions it calls
- Evaluation loops in `<EstimatorModule>` — called O(N) per cycle
- Distribution / aggregation loops — called O(N×M) per cycle
- Any function called O(N) or O(N×M) times per cycle with large N

---

## Forbidden in hot paths — [ERROR]

| Pattern | Alternative |
|---|---|
| `new` / `delete` | Pre-allocated pools, stack allocation, reserve at init |
| `std::make_shared` / `std::make_unique` | Pre-allocated objects |
| `std::vector::push_back` without prior `reserve` | Reserve at init, use fixed-size arrays |
| `std::map` / `std::unordered_map` | Flat sorted `std::vector<pair>`, pre-built lookup table |
| `std::string` construction | `std::string_view`, pre-computed strings |
| Virtual dispatch in tight inner loop | Templates, policy-based design, static dispatch |
| Logging or I/O | Conditional compile-time logging only (`#ifdef DEBUG`) |
| Recursive calls without depth bound | Iterative with explicit stack |

---

## Warned in hot paths — [WARN]

| Pattern | Note |
|---|---|
| N×M nested loops | Must have explicit complexity bound and justification |
| Repeated recomputation of expensive values | Should be cached and invalidated |
| `std::sort` on large containers | Consider pre-sorting or incremental maintenance |

---

## Cache invalidation pattern

Caches in hot paths must follow this pattern:
```cpp
// Declaration: mutable (cache), initialized empty
mutable std::vector<CostType> m_cache;

// Populate: lazily on first use, outside hot loop
if (m_cache.empty()) { /* build cache */ }

// Invalidate: in BeginTurn() or equivalent lifecycle method
void BeginCycle() { m_cache.clear(); }
```

Document the invalidation point in §spec and in code comments.
