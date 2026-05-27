# Rules: Implementation Spec
# File: .cursor/rules/spec.md
# Applied by: Spec writer, Reviewer

> Completeness requirements and forbidden patterns for implementation specs.

---

## Completeness requirements

A spec is complete when every plan step has a spec entry containing:

| Element | Required | Condition |
|---|---|---|
| Interface declaration | Yes | Every new or modified symbol |
| Pre-conditions | Yes | Every new public function |
| Post-conditions | Yes | Every new public function — must be verifiable |
| Invariants | When applicable | When the symbol participates in a class invariant |
| Performance constraint | Yes | Every symbol — even if "none" |
| Ownership rule | Yes | Every new object or field |
| Threading assumption | Yes | Every new symbol — even if "single-threaded" |
| Determinism rule | When applicable | Every symbol in an AI decision path |
| Integration (called from / calls into) | Yes | Every new symbol |
| Error handling | Yes | Every new public function |

A spec entry with any required element missing is incomplete.
An incomplete spec must not be passed to Test designer or Implementer.

---

## Verifiability requirement

Every post-condition must be verifiable:
- Observable as state ("returns empty vector when input is empty")
- Measurable ("GetCost() returns same value for same input after caching")
- Checkable by Reviewer reading the code

Forbidden post-condition forms:
- "works correctly" — not verifiable
- "behaves as expected" — not verifiable
- "updates the state appropriately" — not verifiable
- "handles errors properly" — not verifiable

---

## Scope rules

- Spec must not add symbols not in §plan
- Spec must not change the implementation approach from §plan
- Spec must not add new functionality not in §request
- If specifying a plan step reveals missing scope → escalate to developer, do not add silently

---

## Constraint citation rule

Every constraint in §spec must reference its source:
- Performance constraint → cite `rules/hotpath.md` or specific §architecture rule
- Ownership rule → cite `rules/cpp.md` or specific §architecture pattern
- Determinism rule → cite `rules/determinism.md`
- ABI rule → cite `rules/abi.md`

A constraint without a source citation cannot be verified in code review.

---

## Error handling consistency rule

Error handling must follow the existing pattern of the module being modified.
Do not introduce a new error handling style (exceptions vs asserts vs return codes)
without an explicit architectural decision in §architecture.

Check the module's existing pattern before specifying error handling.

---

## Interface specification rules

- Every new public function must have a complete C++ declaration in the spec
- Parameter types must include const/ref qualifiers
- Return types must be explicit — no "auto" in spec declarations
- noexcept must be specified if the function must not throw (hot-path functions)
- Default arguments are part of the interface — must be specified if used

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| "Implement X appropriately" | Leaves decision to Implementer |
| "Similar to existing Y" | Implementer must read two places — specify directly |
| Post-condition "works correctly" | Not verifiable |
| Error handling "TBD" | Implementer makes inconsistent choices |
| Constraint without source citation | Cannot be verified in review |
| Spec entry for a symbol not in §plan | Scope creep — flag to developer |
| Interface with implicit types | Ambiguous — specify fully |

---

## Stop condition

Spec is ready for Test designer when:
- All plan steps have complete spec entries
- All post-conditions are verifiable
- All constraints have source citations
- No spec entry leaves a non-trivial decision to Implementer

Spec is final (ready for CP3) when:
- Test designer confirms spec is sufficient for test design
- All Test designer feedback is incorporated or escalated
