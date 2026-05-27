# Skill: Implementation Planning
# File: .cursor/skills/planning.md
# Used by: Planner

> Algorithm for producing a complete, ordered, implementable step-by-step plan.
> Goal: every step is specific enough for Implementer to execute without ambiguity.
>
> [SETUP] Update the risk assessment section and step templates with your project's
> actual hot paths, binding layer, and module names.

---

## Core principle

A plan step is not a description of intent — it is a specification of action.
"Update the evaluation logic" is intent.
"Add `EvalCache` field to `Manager`, initialize in `Manager::Init()`, invalidate in `Manager::Reset()`" is a step.

If Implementer would need to make a non-trivial decision to execute a step — the step is too vague.

---

## Algorithm

### Phase 1: Extract constraints from §architecture

Before writing any steps, build a constraint list:

```
Affected modules: [list]
New/changed symbols: [list with signatures]
Forbidden patterns: [list from §architecture]
Invariants that must hold: [list]
ADR constraints: [list]
```

This list is the guardrail. Every step must respect all items on it.

### Phase 2: Identify the change surface

For each architectural change, determine:
- Which files need to change?
- Which symbols are added, modified, or removed?
- What is the minimum set of changes to make the code correct?

Change surface = headers + sources + tests + bindings + examples
Map each symbol change to all files that reference it.

### Phase 3: Order the steps

Determine dependency order using these rules:

1. Internal implementation changes that don't affect public API first
2. Public header changes before any code that uses the new interface
3. Implementation updates to match headers before tests
4. Tests before bindings
5. Bindings before examples
6. Refactoring steps always precede feature steps (never mixed)

For each step, verify: "If I apply only steps 1..N-1, does the codebase compile?"
If not — reorder.

### Phase 4: Write each step

For each step, specify:

```
Step N: <verb phrase — what changes>
  Files: <explicit list — no "and related files">
  What: <specific change — function name, field name, parameter change>
  Why: <which §architecture decision or constraint this implements>
  Risk:
    ABI: none | additive (new symbol) | breaking (changed/removed symbol)
    Perf: none | hot-path affected (specify which path)
    Det: none | decision path affected (specify)
    Bindings: none | affected (specify what changes in binding layer)
  Depends on: step N | none
```

### Phase 5: Verify the plan

After writing all steps:

- Forward simulation: mentally apply each step in order. Does the codebase compile after each step?
- Coverage check: does the sequence of all steps fully implement §request §goal?
- Constraint check: does any step violate §architecture constraints?
- Completeness check: are test updates, binding updates, and example updates included?

---

## Risk assessment guide

### ABI risk
ABI breaks when: function signature changes, class layout changes (new non-static data member,
virtual function added/reordered), enum value changes, typedef changes in public headers.
ABI is additive when: new function overload added, new non-virtual method added,
new class added, new enum value appended at end.

### Performance risk
<!-- SETUP: Replace with actual hot-path entry points for your project. -->
Hot paths in this project: see `memory/architecture/map.md` for the authoritative list.
Any change to these paths requires explicit performance risk assessment.
Flag: "hot-path affected — verify no allocation introduced."

### Determinism risk
Any change to: iteration order over containers, RNG usage, ordering of selection,
ordering of distribution. Flag: "decision path affected — verify stable ordering."

### Binding risk
<!-- SETUP: Replace with actual public API header paths and binding file paths. -->
Triggered by: any change to public API symbols, new enum values, changed function signatures.
Flag: "binding layer affected — binding update required at step N."

---

## Common step templates

<!-- SETUP: Replace the placeholder paths with actual file paths from your project. -->

**Add a field to a class:**
```
Step N: Add <field_name> field to <ClassName>
  Files: <source-dir>/<file>.h, <source-dir>/<file>.cpp
  What: Add <Type> <field_name> to <ClassName>; initialize in <ClassName>::<InitMethod>()
  Why: <§architecture reference>
  Risk: ABI: none (internal), Perf: none, Det: none, Bindings: none
  Depends on: none
```

**Change a public method signature:**
```
Step N: Change signature of <ClassName>::<method>()
  Files: <include-dir>/<header>.h, <source-dir>/<impl>.cpp, <tests-dir>/<test>.cpp, <bindings-dir>/bindings.cpp
  What: Add parameter <Type> <name> to <method>(); update all call sites
  Why: <§architecture reference>
  Risk: ABI: breaking, Perf: none, Det: none, Bindings: affected — .def() update required
  Depends on: none
```

**Add a new component:**
```
Step N: Implement <ComponentName> class
  Files: <source-dir>/<ComponentName>.h, <source-dir>/<ComponentName>.cpp, <source-dir>/<Registry>.cpp
  What: Create <ComponentName> implementing <Interface>; register in <Factory>
  Why: <§architecture reference>
  Risk: ABI: none (internal), Perf: none, Det: verify stable insertion order, Bindings: none
  Depends on: step N-1 (if base class changed)
```
