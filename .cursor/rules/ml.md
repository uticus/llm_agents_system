# Rules: ML Implementation
# File: .cursor/rules/ml.md
# Applied by: Implementer: ML, Reviewer, Architect

> Rules for ML components in this project.
> ML components are subject to all C++ rules PLUS these additional constraints.
>
> [SETUP] Update the pipeline integration rule to reflect the actual data flow
> of your project. Replace <RNG provider> with your project's centralized RNG.

---

## Scope rule

ML in this project is inference only.
Training, model storage design, and dataset management are out of scope
per `memory/project/brief.md §What the project does NOT do`.

If §spec requires training → stop and flag to developer.

---

## Determinism rule (critical)

ML inference must be deterministic:
- Same input + same seed → identical output, always
- No sampling at inference time (no dropout, no stochastic layers)
- No floating-point non-determinism from operation ordering
- RNG: use the project's centralized RNG — never `std::rand()` or `std::random_device`

Determinism test is mandatory for every ML component.
Non-deterministic ML output is an architectural violation ([ERROR]).

---

## Pipeline integration rule

<!-- SETUP: Replace the data flow rule with your project's actual pipeline. -->

ML output must flow through the established processing pipeline.
Direct action execution from ML output is forbidden.

```
Allowed:   ML → score/priority → [pipeline layer] → output
Forbidden: ML → action → output  (bypasses pipeline — architectural violation)
```

ML components belong to the estimation/evaluation layer:
- Pure evaluators — no side effects
- No command emission
- No state mutation in core data structures

---

## Performance rules

Apply all rules from `rules/hotpath.md` PLUS:

- Feature extraction: pre-allocate feature vector at init — do not resize during inference
- Model inference: no dynamic allocation — use pre-allocated buffers
- If inference is in hot path: benchmark against cycle budget
- If inference is too slow for hot path: move to pre-computation phase
  (compute once per cycle start, cache result, use in hot path)

---

## Container rules

All rules from `rules/determinism.md` apply. Additionally:
- Feature vectors must be constructed in deterministic order
- If features are derived from state collections — sort before extracting
- Model weight containers must not use hash-based structures

---

## Integration rules

- ML component receives input via the established project interface
- ML component must not access internals directly
- ML component output range and format must match §spec exactly
- ML component must be testable in isolation (unit tests without full state setup)

---

## Metric rules

- Every ML component must have at least one quality metric in §test-criteria
- Determinism metric is always required
- Metric thresholds must come from §test-criteria — never set arbitrarily
- If metric threshold is not achievable → escalate, do not change threshold

---

## Forbidden patterns

| Pattern | Why forbidden |
|---|---|
| Model training code | Out of scope |
| `std::random_device` or `std::rand()` in inference | Non-deterministic |
| Dropout or sampling at inference | Non-deterministic |
| Direct action execution from ML output | Violates pipeline architecture |
| Dynamic allocation in inference hot path | Violates rules/hotpath.md |
| Unordered containers in decision paths | Non-deterministic iteration |
| Hardcoded metric threshold | Must come from §test-criteria |
| Changing metric threshold to pass test | Masks quality problem |
