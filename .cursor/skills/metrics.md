# Skill: ML Metrics
# File: .cursor/skills/metrics.md
# Used by: Implementer: ML, Test designer

> How to define and verify ML metrics for project components.
> Goal: precise, domain-relevant metrics that verify ML component quality.
>
> [SETUP] Update the "Domain-specific metrics" section after reading memory/project/domain.md.
> Replace the game AI examples with metrics relevant to your project.

---

## Metric types

| Metric type | When to use | Formula |
|---|---|---|
| Accuracy | Classification: is the correct category selected? | correct / total |
| Mean Absolute Error | Regression: score or priority estimation | mean(\|predicted - actual\|) |
| Rank correlation | Ordering: ranking matches expected order | Spearman ρ |
| Output quality delta | End-to-end: does ML improve overall output quality? | quality_with_ML - quality_without |
| Determinism check | Always | 3 identical runs → identical output |

---

## Metric definition requirements

Every metric in §test-criteria must specify:

```
Metric: <name>
Type: accuracy | MAE | rank_correlation | quality_delta | determinism
Dataset: <description of test inputs — how many, which scenarios>
Threshold: <specific value — not "as good as possible">
Measurement: <how to compute — exact formula or function name>
Baseline: <what "no ML" produces — for comparison>
```

---

## Determinism metric (always required)

```
Metric: output_determinism
Type: determinism
Dataset: 3 runs with identical input state and seed S
Threshold: byte-identical output across all 3 runs
Measurement: diff(run1_output, run2_output) == empty
             diff(run1_output, run3_output) == empty
```

This metric is always required for any ML component.
Non-deterministic ML output is an architectural violation.

---

## Threshold rules

1. Thresholds must come from §test-criteria — never set arbitrarily
2. If no threshold is specified in §spec — ask developer or Spec writer before proceeding
3. If threshold cannot be met — escalate to developer; do not lower the threshold to pass
4. Placeholder threshold: "no regression from current baseline" — use only when no baseline exists

---

## Domain-specific metrics

<!-- SETUP: Replace the examples below with actual domain-relevant metrics.
     After reading memory/project/domain.md, fill in the relevant metric types
     and example queries for your project. -->

Examples of domain-specific metrics to consider:
- Classification metrics: does the component select the correct category?
- Ordering metrics: does the component rank items in the expected order?
- End-to-end metrics: does the component improve the overall observable output quality?
- Regression metrics: does the component predict the correct numerical value?

When defining metrics, specify:
- Which domain scenarios (from domain.md) are used as the test dataset
- What "correct" means in domain terms
- How to measure it programmatically

---

## Measurement implementation

```python
# Accuracy
def measure_accuracy(predictions, ground_truth):
    assert len(predictions) == len(ground_truth)
    correct = sum(p == g for p, g in zip(predictions, ground_truth))
    return correct / len(predictions)

# MAE
def measure_mae(predictions, ground_truth):
    assert len(predictions) == len(ground_truth)
    return sum(abs(p - g) for p, g in zip(predictions, ground_truth)) / len(predictions)

# Rank correlation (Spearman)
from scipy.stats import spearmanr
def measure_rank_correlation(predicted_ranks, actual_ranks):
    rho, _ = spearmanr(predicted_ranks, actual_ranks)
    return rho
```
