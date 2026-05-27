# Rules: Code Review
# File: .cursor/rules/review.md
# Applied by: Reviewer

> Severity levels, blocking criteria, and review process rules.

---

## Severity levels

| Severity | Definition | Effect on loop |
|---|---|---|
| [BLOCKING] | Implementation incorrect, unsafe, spec-non-compliant, or arch-violating | Loop continues — must be fixed |
| [WARNING] | Functional but suboptimal, incomplete documentation, minor risk | Recorded — loop may complete |
| [QUESTION] | Cannot assess without clarification | Loop pauses — stops AGREE |

---

## What is always [BLOCKING]

- Any §spec post-condition not satisfied
- Any §spec interface not matched (wrong signature, wrong return type)
- Any architectural invariant violated (plan-centricity, phase separation, layer boundary)
- Any hot-path allocation introduced
- Any determinism violation (unordered_* in decision path, unstable sort)
- Any raw owning pointer in new code
- Any C++ exception reaching Python binding unmapped
- Any ABI breaking change without ADR
- Any test that is a false positive (always passes regardless of implementation)
- Any §test-criteria scenario with no corresponding test
- Any regression in existing tests

---

## What is never [BLOCKING]

- Style preferences not in rules/cpp.md
- Naming conventions followed in the module (even if Reviewer prefers different)
- Performance optimizations not required by §spec
- Adding more tests than §test-criteria requires (additive is ok)
- Documentation more verbose than required

---

## Re-raise rules

- Do not re-raise an issue validly resolved in a previous iteration
- An issue is validly resolved when Implementer's change directly addresses it
- If resolution is insufficient — raise the original issue again with explanation
- Track: 3 times same issue unresolved → escalate to developer

---

## Iteration rules

- Read full implementation from scratch every iteration
- Do not carry assumptions from previous iterations
- A change may affect code reviewed in previous iteration — always re-check
- Append feedback to session file — do not overwrite previous iterations

---

## Scope rules

- Review only changed files and their direct dependencies
- Do not raise issues about unrelated existing code
  (unless the change broke something in that code)
- If unrelated code has issues — note as [WARNING] and suggest separate task

---

## Stop condition

Reviewer writes AGREE only when:
- Zero [BLOCKING] issues after full evaluation of all six categories
- All previous [BLOCKING] issues confirmed resolved
- Evaluation performed from scratch on current iteration

Loop stop condition requires BOTH:
- Reviewer AGREE (zero [BLOCKING])
- Tester AGREE (all §test-criteria pass)
