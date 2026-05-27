# Rules: Determinism
# File: .cursor/rules/determinism.md
# Applied by: Test designer, Tester, Implementer, Architect, Reviewer

> [WARNING] Strict output determinism is NOT a hard invariant for this project.
> LLM responses are non-deterministic by nature. Reproducibility is achieved by
> recording and replaying run traces (see the replay_analysis subsystem), not by
> enforcing bit-identical outputs. The rules below apply only to internal, non-LLM
> logic (e.g. plan ordering, tool dispatch) that should behave deterministically given
> the same inputs. Do not assert exact-match equality on LLM outputs in tests.

---

## Core rule

Same input state + same seed → identical output sequence.
This applies to every code path that influences observable output.

---

## What must be deterministic

<!-- SETUP: Replace with the actual decision paths in your project. -->

- All ordering and priority computation
- All selection and ranking logic
- All output of the primary processing entry point(s)

---

## Sources of non-determinism to avoid

| Source | Rule |
|---|---|
| `std::unordered_map` / `std::unordered_set` iteration | Forbidden in decision paths — use sorted containers or `std::map` |
| Pointer values as sort keys | Forbidden — pointer addresses are non-deterministic |
| `std::sort` on equal elements without stable tie-breaking | Use `std::stable_sort` or add deterministic tie-breaking key |
| System time in decision logic | Forbidden |
| Thread scheduling | Forbidden — single-threaded execution assumed |
| Uninitialized memory reads | Forbidden — undefined behavior |
| Hash map iteration order | Forbidden in decision paths — iteration order is not guaranteed |

---

## RNG rules

<!-- SETUP: Replace with the actual RNG provider in your project. -->

- All random number generation must use the centralized RNG provided by the project
- RNG must be explicitly seeded before use
- RNG state must be part of the serializable state if reproducibility is required
- No use of `std::rand()`, `rand()`, or system random sources in decision code

---

## Verification requirements

Any change to a decision path must include a determinism test scenario:
- Run the processing entry point with the same state and seed S at least 3 times
- Compare output sequences — must be byte-identical
- Additionally: verify stability under randomized container iteration in debug build

---

## Allowed non-determinism

Non-determinism is allowed only when:
- Explicitly documented in §architecture as intentional
- Isolated from the output path (e.g. logging, diagnostics)
- Approved by developer via an ADR

Any undocumented non-determinism in output is an architectural violation.
