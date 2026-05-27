# Skill: Implementation Spec Writing
# File: .cursor/skills/spec-writing.md
# Used by: Spec writer

> Algorithm for translating a plan step into a precise implementation specification.
> Goal: Implementer can execute every spec entry without making non-trivial decisions.

---

## Core principle

A spec entry is not a description of intent — it is a contract.
"Add a cache to improve performance" is intent.
"Add `mutable std::vector<CostType> m_cache` to `MovementEstimator`;
initialize empty in constructor; populate on first call to `GetCost()`; invalidate
in `BeginCycle()` by calling `m_cache.clear()`" is a spec.

The test for a good spec: if Implementer reads only §spec (not §plan or §architecture),
can they implement correctly? If yes — spec is sufficient.

---

## Algorithm

### Phase 1: Decompose each plan step

For each plan step, extract:
1. New symbols to create (classes, functions, fields, enums)
2. Existing symbols to modify (signature change, behavior change, ownership change)
3. Symbols to delete or deprecate
4. Integration points (what calls this, what this calls)
5. Constraints (from §architecture: hot-path, ownership, determinism, ABI)

### Phase 2: Specify interfaces

For each new or modified symbol:

**Functions and methods:**
```cpp
// Full declaration
ReturnType ClassName::methodName(
    const ParamType& param1,
    ParamType2 param2
) const noexcept;
```
Specify: name, parameters (with types and const/ref qualifiers), return type,
const-ness, noexcept if relevant. Do not leave types implicit.

**Classes and structs:**
```cpp
class NewClass : public BaseClass {
public:
    explicit NewClass(ContextType& ctx);
    ReturnType method(ParamType p) const;
private:
    FieldType m_field;
};
```
Specify: inheritance, constructor parameters, public interface, key private fields
relevant to the contract.

**Fields:**
```
<ClassName>:
  add: mutable std::vector<CostType> m_cache
  initialize: empty in constructor
  lifetime: invalidated by BeginCycle()
```

### Phase 3: Write contracts

For each symbol, write observable contracts:

**Pre-conditions:** what must be true when this is called
- "ctx must be initialized (ctx.IsReady() == true)"
- "plan must not be null"
- "index must be in range [0, size())"

**Post-conditions:** what must be true after this returns
- "returns empty vector if input has no valid moves"
- "m_cache is non-empty after first call"
- "caller owns the returned unique_ptr"

Write post-conditions as observable state — not as intent.
Bad: "correctly updates the plan"
Good: "plan.GetPriority() > 0 after call if plan.HasTargets()"

**Invariants:** what must always be true regardless of call history
- "m_cache.size() == m_unitCount or m_cache.empty()"
- "sum of all resource bindings does not exceed budget"

### Phase 4: Specify constraints

For each spec entry, check all four constraint dimensions:

**Performance:**
- Is this called in the AI tick loop? → "no allocation permitted"
- Does this build a table? → "build once, read many — cache result"
- Cite the rule: "per rules/hotpath.md — no heap allocation in Execute()"

**Ownership:**
- Who creates this object? Who destroys it?
- Is it owned (unique_ptr), shared (shared_ptr), or referenced (raw ref)?
- Cite the rule: "per rules/cpp.md — no raw owning pointers"

**Threading:**
- "single-threaded — no synchronization required"
- "called only from AI turn thread"

**Determinism:**
- Is this in an AI decision path? → "iteration must use stable ordering"
- "results must be identical given same input and same RNG seed"
- Cite the rule: "per rules/determinism.md — stable container iteration required"

### Phase 5: Specify error handling

For every new public function:
- Invalid input: assert, exception, or return value? Which?
- Null pointer: assert in debug, undefined behavior in release? Or check always?
- Out-of-range: clamp, assert, or exception?

Be consistent with existing patterns in the module.
If the module uses asserts — use asserts. Do not introduce a new error handling style.

### Phase 6: Specify integration

For each spec entry:
- Called from: list existing callers (from the dependency analysis in §plan)
- Calls into: list what this code will call
- Replaces: if this supersedes existing code, name what it replaces

---

## Verifiability check

Before finalizing each spec entry, verify:
- Can Test designer write a test that passes only when the post-condition is met?
- Can Reviewer verify the constraint is satisfied by reading the code?
- Would two different Implementers produce compatible implementations from this spec?

If any answer is "no" — the spec entry needs more precision.

---

## Common patterns for this project

**Adding a field with lazy initialization:**
```
Field: mutable CacheType m_cache
Init:  default-constructed (empty) in ClassName constructor
Populate: on first call to GetX() if m_cache.empty()
Invalidate: in BeginCycle() — call m_cache.clear()
Thread: single-threaded, no lock needed
Alloc: population happens outside hot path — one-time per cycle
```

**Adding a new component:**
```
Class: NewComponent : public BaseInterface
Constructor: (ContextType& ctx, Params params)
Required overrides: IsUsable(), GetEffectiveness(), Execute()  [adapt to actual interface]
Registration: add to Factory::Create() — append at end (stable order)
Ordering: deterministic — use index-based sort, not pointer comparison
```

**Modifying a public method signature:**
```
<!-- SETUP: Replace with actual public header and binding file paths. -->
Old: void PublicClass::OldMethod()
New: void PublicClass::OldMethod(NewParamType param = DefaultValue)
ABI: additive — default value preserves binary compatibility
Callers: list all — from §plan step file list
Bindings: add parameter to .def() in <bindings-file>
```
