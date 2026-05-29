# evaluation/prompts

## Overview

The `evaluation/prompts` module provides tooling for data-driven prompt engineering: it enables developers to define multiple prompt variants, run them all against the same evaluation case set using a shared LLM router, and receive a ranked comparison that identifies the best-performing variant. The module exists because prompt wording has a large and often surprising effect on LLM output quality. Relying on manual inspection to compare prompt drafts is error-prone and slow; this module replaces that process with a repeatable, metric-driven A/B evaluation loop. It sits one level above the `evaluation/framework` module, reusing its harness and aggregation logic while adding the concept of a named, formattable prompt template.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `PromptVariant` | dataclass | A named prompt template with `{input}` placeholder. |
| `VariantResult` | dataclass | Pairs a `PromptVariant` with its aggregated `EvalReport`. |
| `PromptComparison` | dataclass | Ranked collection of `VariantResult` objects, sorted by mean score. |
| `compare` | async function | Evaluate all variants over shared cases and return a `PromptComparison`. |

### PromptVariant

```
PromptVariant(
    name: str,
    template: str,
    metadata: dict[str, Any] = {},
)

format(input_text: str) -> str
```

`template` must contain `{input}`. `format` calls `str.format_map({"input": input_text})` and returns the rendered prompt string.

### VariantResult

```
VariantResult(
    variant: PromptVariant,
    report: EvalReport,
)

mean_score -> float   # property, alias for report.mean_score
```

### PromptComparison

```
PromptComparison(
    results: list[VariantResult],   # sorted descending by mean_score at __post_init__
)

winner -> PromptVariant | None   # property, highest-scoring variant or None if empty
```

### compare (async function)

```
async compare(
    variants: list[PromptVariant],
    cases: list[EvalCase],
    router: Any,
    metric: Any,
    model: str = "default",
    repeat: int = 1,
    threshold: float = 0.5,
) -> PromptComparison
```

For each variant: wraps the variant's formatted prompt in an `LLMRequest`, calls `router.complete`, scores the response with `metric`, and aggregates results into a `VariantResult`. Returns all variant results ranked by `mean_score` descending.

---

## Architecture

### Conceptual view

```
  list[PromptVariant]      list[EvalCase]
          |                      |
          +----------+----------+
                     |
                  compare()
                  /       \
        for each variant:
           PromptVariant.format(input)
                  |
              LLMRequest
                  |
            router.complete()
                  |
             EvalHarness
                  |
              aggregate()
                  |
           VariantResult
                  |
         PromptComparison
         (sorted by score)
```

### Data flow

1. The caller provides a list of `PromptVariant` objects (each with a distinct template) and a shared `list[EvalCase]`.
2. `compare` iterates over variants. For each variant it constructs a closure `agent_fn(input_text)` that:
   a. Calls `variant.format(input_text)` to produce the rendered prompt.
   b. Wraps the prompt in an `LLMRequest` (model, messages, etc.).
   c. Awaits `router.complete(request)` and returns `response.content`.
3. An `EvalHarness` is built per variant using the closure and the shared `metric`. `harness.run(cases, repeat=repeat)` executes the agent for every case.
4. `aggregate(results, threshold)` produces an `EvalReport` for the variant.
5. A `VariantResult(variant, report)` is appended to the collection.
6. After all variants are processed, `PromptComparison(results=variant_results)` is constructed. `__post_init__` sorts results descending by `mean_score`.
7. The caller inspects `comparison.winner` or iterates `comparison.results` to examine ranked variants.

### Key abstractions

**PromptVariant** separates the identity of a prompt (its `name` and `metadata`) from its content (`template`). The `format` method uses `str.format_map` with a single key `"input"`, keeping the template format minimal and avoiding conflicts with other curly braces in the prompt text that do not correspond to substitution sites.

**VariantResult** is a thin pairing of a variant with its `EvalReport`. The `mean_score` property exists purely as a convenience to avoid spelling out `result.report.mean_score` in sorting and display code. It delegates directly to `EvalReport.mean_score` with no additional logic.

**PromptComparison** performs ranking at construction time via `__post_init__`. This design keeps ranking logic out of `compare` and out of the caller, and ensures that any code receiving a `PromptComparison` always sees a consistently ordered collection. The sort is stable (Python's `sorted` is stable), so ties among variants with equal scores preserve insertion order.

**Closure capture in compare**: the inner `_make_agent(v)` factory function is used to capture each variant by value in the loop. Without this factory, a naive lambda or inner `async def` in a loop would capture the loop variable by reference, causing all closures to use the last variant at call time. The factory pattern avoids this classic Python late-binding issue.

---

## Design decisions and tradeoffs

- **Decision**: One `EvalHarness` instance is created per variant rather than sharing a single harness. **Why**: Each variant requires a different `agent_fn` closure that encodes the specific template. Sharing a harness would require passing the variant through every `run` call, which would complicate the harness interface. **Tradeoff**: Harness construction cost is paid N times, which is negligible but could be simplified if the harness ever became expensive to initialize.

- **Decision**: `compare` imports `LLMRequest` at call time from `llm_agents.infra.inference_routing._models` rather than at module level. **Why**: Avoids a hard import-time dependency on the infrastructure layer; the prompts module can be imported in isolation (e.g., for unit tests that mock the router). **Tradeoff**: The import error is deferred to runtime if the infrastructure module is missing, making dependency failures less obvious at startup.

- **Decision**: The `router` and `metric` parameters are typed as `Any`. **Why**: Keeps the prompts module decoupled from the specific router and metric implementations; any object with the right method signatures works. **Tradeoff**: Static type checkers cannot verify correctness of router or metric objects passed by callers.

- **Decision**: Sorting is done at `PromptComparison` construction time. **Why**: Sorting once at construction is cheaper than sorting on every access. **Tradeoff**: If a caller adds additional `VariantResult` objects to `comparison.results` after construction the ordering guarantee is violated; the list is mutable.

---

## Scaling concerns

Each call to `compare` runs `len(variants) * len(cases) * repeat` LLM API calls sequentially. With N=5 variants, 50 cases, and repeat=3, that is 750 sequential LLM calls. At 500 ms per call (a modest estimate for a hosted model), this takes over 6 minutes. There is no parallelism across variants or cases. Memory usage is bounded by `len(variants) * len(cases) * repeat` `EvalResult` objects, which is typically negligible.

**What breaks first**: wall-clock runtime for large variant sets or large case sets.

**Ceiling**: practical ceiling in interactive use is roughly 3-5 variants with 20-50 cases. Beyond that, users need concurrent evaluation.

---

## Future improvements

- **Parallel variant evaluation**: run variants concurrently with `asyncio.gather` rather than sequentially. Variants are independent and their evaluation can be fully parallelized up to the API rate limit.
- **Statistical significance testing**: add a `significant_winner` property to `PromptComparison` that performs a paired t-test or bootstrap confidence interval over per-case scores across the top two variants, so the winner designation carries a confidence level.
- **Template validation**: add a `PromptVariant.validate()` method that checks whether `{input}` is present in the template and warns about unrecognized format keys, catching template errors before running expensive API calls.
- **Result persistence**: add a `PromptComparison.to_json()` / `from_json()` round-trip so comparison results can be stored and compared across code changes.
- **Multi-turn support**: extend `PromptVariant` to support multi-turn message sequences, not just single-turn prompts, to support evaluation of chat-style agents.

---

## Usage examples

Basic two-variant comparison:

```python
import asyncio
from llm_agents.evaluation.prompts import PromptVariant, compare
from llm_agents.evaluation.framework import EvalCase, ContainsMetric

v1 = PromptVariant(name="direct", template="Answer briefly: {input}")
v2 = PromptVariant(name="cot", template="Think step by step, then answer: {input}")

cases = [
    EvalCase(input="What is 2+2?", expected_output="4"),
    EvalCase(input="Capital of France?", expected_output="Paris"),
]

comparison = asyncio.run(compare([v1, v2], cases, router=my_router, metric=ContainsMetric()))
print(comparison.winner.name)
```

Inspecting all ranked results:

```python
for variant_result in comparison.results:
    print(
        f"{variant_result.variant.name}: "
        f"mean={variant_result.mean_score:.3f}, "
        f"pass_rate={variant_result.report.pass_rate:.2f}"
    )
```

Using repeat for variance estimation:

```python
comparison = asyncio.run(
    compare([v1, v2], cases, router=my_router, metric=ContainsMetric(), repeat=5, threshold=0.6)
)
winner = comparison.winner
best_report = comparison.results[0].report
print(f"Winner: {winner.name}, std={best_report.std_score:.3f}")
```
