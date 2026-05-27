# Skill: ML Component Implementation
# File: .cursor/skills/impl-ml.md
# Used by: Implementer: ML

> Algorithm for implementing ML components.
> Goal: deterministic, pipeline-integrated, metric-verified ML code.
>
> [SETUP] Replace placeholder type names and RNG references with project-specific ones.
> See memory/architecture/map.md for the pipeline integration points.

---

## Core principle

ML in this project is inference only — no training.
The ML component is an evaluator or decision enhancer within the established pipeline.
It must satisfy the same constraints as any other evaluator:
- Deterministic output for same input and seed
- No side effects
- No allocation in hot paths
- Output flows through the pipeline — not directly to execution

---

## Algorithm

### Phase 1: Understand the integration point

Before writing any ML code, identify from §spec:
- Where in the pipeline does this component sit?
  (Estimation layer? Distribution layer? Planning layer?)
- What is its input? (State subset, priorities, element data?)
- What is its output? (Score, priority delta, feature vector?)
- Who calls it? (Which module invokes this component?)
- How does its output affect downstream processing? (Via which method or field?)

If integration point is unclear → flag to Spec writer before coding.

### Phase 2: Determinism first

Before implementing any ML logic, establish the determinism foundation:

```cpp
// Use the project's centralized RNG — never create your own
class MLComponent {
public:
    // SETUP: Replace ContextType with actual context class
    explicit MLComponent(ContextType& ctx) : m_ctx(ctx) {}

    float Evaluate(const InputType& input) const {
        // Use m_ctx.GetRng() if randomness is needed
        // Prefer deterministic algorithms that need no RNG
    }
private:
    ContextType& m_ctx;  // non-owning reference
};
```

Rules:
- Use the project's centralized RNG if randomness is needed — never `std::rand()` or `std::random_device`
- Prefer deterministic inference algorithms (no sampling, no dropout at inference)
- Container iteration must use stable ordering
- Feature extraction must produce identical output for identical input state

### Phase 3: Feature extraction

Extract features from state per §spec:

```cpp
// SETUP: Replace IGameInterface and ContextType with actual project types
FeatureVector ExtractFeatures(const IGameInterface& state,
                               const ContextType& ctx) {
    FeatureVector features;
    features.reserve(kFeatureCount);  // pre-allocate — not in hot path

    // Extract per §spec feature list
    // Use only the public interface — no internal access
    // Features must be deterministic given same state
    return features;
}
```

Feature extraction rules:
- Must use only the public state interface
- Must produce identical result for identical state
- Must extract features in a fixed, deterministic order
- Do not resize during extraction — use `reserve()` at the start

### Phase 4: Inference

```cpp
float MLComponent::Evaluate(const FeatureVector& features) const {
    // Pre-allocated output buffer — set at construction
    // No dynamic allocation during inference
    return RunInference(features, m_weights);
}
```

Inference rules:
- No dynamic allocation — buffers pre-allocated in constructor
- No virtual dispatch in inference path (if hot path)
- No I/O during inference
- Output must be in the range specified by §spec

### Phase 5: Pipeline integration

```cpp
// SETUP: Replace Manager and PlanType with actual project types
// Correct:
// Manager reads ML output and uses it to update priorities
void Manager::UpdatePriorities() {
    for (auto& plan : m_plans) {
        float score = m_mlComponent.Evaluate(ExtractFeatures(m_state, m_ctx));
        plan.AdjustPriority(score);  // output flows through plan
    }
}

// WRONG — direct execution:
// void Manager::ExecuteMLDecision() {
//     float score = m_mlComponent.Evaluate(...);
//     m_executor.Execute(score);  // bypasses pipeline
// }
```

### Phase 6: Metrics verification

After implementation — verify each metric from §test-criteria:

For determinism:
```bash
# Run 1
<test runner> --filter=MLComponent.determinism_test > run1.txt

# Run 2 — same binary, same seed
<test runner> --filter=MLComponent.determinism_test > run2.txt

diff run1.txt run2.txt  # must be empty
```

For accuracy / MAE:
```
Run on test dataset from §test-criteria
Compare against threshold from §test-criteria
If threshold not met → do not change the threshold — escalate to developer
```
