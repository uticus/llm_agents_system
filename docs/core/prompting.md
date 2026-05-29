# prompting

## Overview

The `prompting` module provides building blocks for constructing reusable, structured prompts for LLM agents. It supplies three abstractions at increasing levels of sophistication: a plain template with named placeholders (`PromptTemplate`), a few-shot template that prepends labelled input/output examples before a user query (`FewShotTemplate`), and a dynamic example selector that ranks a pool of candidate examples by relevance to a given query (`ExampleSelector`). The module exists because prompt construction is a recurring concern across every agent capability — planning, tool description, memory queries, classification, and more — and having a shared, tested set of primitives prevents ad-hoc string formatting scattered across the codebase. All classes are pure Python dataclasses or simple objects with no external dependencies, making them usable in any context including offline tests and CLI tools.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `PromptTemplate` | dataclass | Format-string template with named `{placeholder}` slots. |
| `Example` | dataclass | A single (input, output) training example for few-shot prompting. |
| `FewShotTemplate` | dataclass | Instruction + examples + query renderer. |
| `ExampleSelector` | class | Select top-k most relevant examples from a pool using a scorer function. |

### `PromptTemplate`

```python
@dataclass
class PromptTemplate:
    template: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

| Method / Property | Signature | Description |
|---|---|---|
| `format` | `(**kwargs: Any) -> str` | Render the template by substituting kwargs. Raises `KeyError` for missing placeholders. |
| `variables` | property `-> list[str]` | Return placeholder names in order of first appearance, deduplicated. |

### `Example`

```python
@dataclass
class Example:
    input_text: str
    output_text: str
```

### `FewShotTemplate`

```python
@dataclass
class FewShotTemplate:
    instruction: str
    examples: list[Example] = field(default_factory=list)
    input_label: str = "Input"
    output_label: str = "Output"
    query_label: str = "Input"
    separator: str = "\n\n"
```

| Method | Signature | Description |
|---|---|---|
| `format` | `(query: str) -> str` | Render instruction, examples, and final query. |

The rendered structure is:
```
{instruction}
{separator}
{input_label}: {example.input_text}
{output_label}: {example.output_text}
{separator}
...
{query_label}: {query}
{output_label}:
```

### `ExampleSelector`

```python
ExampleSelector(
    examples: list[Example],
    scorer: Any,   # Callable[[str, Example], float]
    top_k: int = 3,
)
```

| Method | Signature | Description |
|---|---|---|
| `select` | `(query: str, *, top_k: int \| None = None) -> list[Example]` | Return top-k examples ranked by descending scorer value. |

The `scorer` callable signature is `(query: str, example: Example) -> float`. Higher scores are preferred. The `top_k` keyword argument in `select` overrides the constructor default for a single call.

---

## Architecture

### Conceptual view

```
  PromptTemplate
    template: str ("You are {role}. Task: {task}")
    metadata: dict
        |
    .format(role="...", task="...")
        |
    rendered prompt string

  Example pool [Example, Example, ...]
        |
  ExampleSelector(examples, scorer, top_k)
        |
    .select(query)
        |
    scored and ranked [Example, ...]
        |
  FewShotTemplate(instruction, selected_examples)
        |
    .format(query)
        |
    rendered few-shot prompt string
```

All components are stateless with respect to rendering. `FewShotTemplate` holds a reference to a list of examples but does not mutate them during `format`. `ExampleSelector` holds a reference to the pool but does not mutate it during `select`.

### Data flow

**PromptTemplate rendering:**

1. Caller creates `PromptTemplate(template="Translate to {language}: {text}")`.
2. Caller calls `tmpl.format(language="French", text="Hello")`.
3. Internally, `str.format_map(kwargs)` is called on the template string.
4. The rendered string is returned.
5. If a placeholder has no matching kwarg, `format_map` raises `KeyError`.

**FewShotTemplate rendering:**

1. Caller creates a `FewShotTemplate` with `instruction`, a list of `Example` objects, and optional label/separator customization.
2. Caller calls `tmpl.format(query="What is 2 + 2?")`.
3. `format` builds a list of parts starting with `instruction`.
4. For each `Example`, a block `"{input_label}: {input_text}\n{output_label}: {output_text}"` is appended.
5. A final block `"{query_label}: {query}\n{output_label}:"` is appended.
6. All parts are joined with `separator` (default `"\n\n"`) and returned.

**ExampleSelector.select:**

1. All examples in the pool are scored using `self._scorer(query, example)` for each example.
2. Examples are sorted by descending score using Python's `sorted` with a key function.
3. The top-k examples are sliced and returned. The pool itself is not modified.
4. The per-call `top_k` argument, if provided, overrides `self.top_k` for that single call.

### Key abstractions

**`PromptTemplate`** — the lowest-level building block. It wraps Python's standard `str.format_map` to provide named placeholder substitution. The `variables` property uses `string.Formatter.parse` to introspect the template string, making it possible to enumerate required inputs without parsing the template string manually. The `metadata` dict allows callers to attach model hints, version tags, or source identifiers alongside the template without polluting the template string itself.

**`Example`** — a simple (input, output) pair. The minimal structure keeps it easy to construct from datasets, JSONL files, or annotation tools. Both fields are plain strings, which means they can contain any format (plain text, JSON, code, etc.) without the template needing to know the structure.

**`FewShotTemplate`** — assembles the three standard sections of a few-shot prompt: task instruction, demonstrations, and the live query. The configurable labels (`input_label`, `output_label`, `query_label`) allow adaptation to different model training formats (e.g. `Human:`/`Assistant:` for chat models, `Q:`/`A:` for QA tasks, `Code:`/`Tests:` for coding tasks).

**`ExampleSelector`** — provides dynamic example selection rather than static example lists embedded in templates. By accepting any scorer callable, it is compatible with simple heuristics (word overlap, string length), embedding-based similarity functions, or model-based scoring, without prescribing an implementation. The `top_k` parameter makes it composable with `FewShotTemplate` by selecting exactly as many examples as the template has room for.

---

## Design decisions and tradeoffs

- **Decision**: `PromptTemplate.format` uses `str.format_map` rather than a custom parser. **Why**: `str.format_map` is part of the Python standard library, is well-tested, and handles edge cases (nested braces, conversion flags, format specs). Building a custom parser would duplicate this work and introduce new bugs. **Tradeoff**: The template syntax is exactly Python's `str.format` syntax, which has quirks (e.g. literal braces must be escaped as `{{` and `}}`). Non-Python users writing templates may find this surprising.

- **Decision**: `PromptTemplate.variables` deduplicates placeholders in order of first appearance. **Why**: Duplicate placeholders in a template string are valid Python format strings (both instances are filled with the same value), but exposing duplicates in `variables` would confuse callers trying to enumerate required inputs. **Tradeoff**: If a template intentionally uses the same placeholder twice for emphasis or structure, `variables` will report it only once.

- **Decision**: `FewShotTemplate.format` appends `"{output_label}:"` without a space at the end of the final query block. **Why**: This is the standard continuation format used in most few-shot prompting research: the model is expected to continue from where `Output:` ends, making it clear that the next token should be the start of the output. **Tradeoff**: For chat-API models that use a structured `messages` format, the rendered string may need to be split into separate messages, which the template does not support.

- **Decision**: `ExampleSelector.scorer` is injected as a constructor argument rather than defined in a protocol. **Why**: Scorer implementations vary widely (embedding similarity, BM25, TF-IDF, model-based scoring) and a protocol would impose a method name that existing similarity libraries do not follow. A plain callable is more flexible. **Tradeoff**: Type checking for the scorer is minimal. A scorer with the wrong signature fails only at call time with a cryptic `TypeError`.

- **Decision**: `ExampleSelector` sorts the entire pool on every `select` call. **Why**: Keeps the implementation simple and correct for pools of typical size (dozens to hundreds of examples). Pre-sorting is not possible because scores depend on the query. **Tradeoff**: For large pools (thousands of examples) and high-frequency selection, per-call full sort is O(n log n) and may become a bottleneck.

---

## Scaling concerns

- `PromptTemplate.format` is O(len(template)) and essentially instant.
- `PromptTemplate.variables` uses `string.Formatter.parse`, which is O(len(template)). For typical prompt templates (under 1,000 characters), this is negligible.
- `FewShotTemplate.format` is O(total length of instruction + examples + query). For hundreds of examples, the rendered string can become very large and may itself exceed the model's context window.
- `ExampleSelector.select` is O(n log n) in pool size. For pools under 10,000 examples with a fast scorer (e.g. word overlap), selection is under 50 ms. For embedding-based scorers that require a model forward pass per example, scaling requires batched scoring outside of `select`.
- There are no caching mechanisms. Repeated `select` calls with the same query score all examples from scratch each time. An LRU cache on the scoring result keyed by `(query, example.input_text)` would improve repeated lookups.

---

## Future improvements

- **Batched scoring in `ExampleSelector`**: Add an optional `batch_scorer: Callable[[str, list[Example]], list[float]]` parameter that scores all examples in a single call (e.g. a vectorized embedding similarity), replacing the per-example loop for high-latency scorers.
- **Template validation at construction time**: In `PromptTemplate.__post_init__`, attempt a dry-run `format_map` with placeholder names as values to detect malformed template strings early rather than at render time.
- **Token-budget-aware example selection in `FewShotTemplate`**: Add a `max_example_tokens: int` parameter and a `tokenizer` to `FewShotTemplate.format` so that examples are included only until the budget is reached, preventing context overflow for large example pools.
- **Structured output templates**: Add a `JSONTemplate` subclass of `PromptTemplate` that renders a JSON structure with placeholder fields, for models that reliably produce structured JSON outputs.
- **Template registry**: Provide a `TemplateRegistry` class (analogous to `ToolRegistry`) that stores named templates and allows retrieval by name, enabling configuration-driven prompt management.

---

## Usage examples

**Basic variable substitution with `PromptTemplate`:**

```python
from llm_agents.core.prompting import PromptTemplate

tmpl = PromptTemplate(
    template="You are a {role}. Answer the following question concisely.\n\nQuestion: {question}",
    metadata={"version": "1.0", "model_hint": "gpt-4o"},
)

print("Variables:", tmpl.variables)  # ['role', 'question']

prompt = tmpl.format(role="Python expert", question="What is the GIL?")
print(prompt)
```

**Few-shot prompt construction:**

```python
from llm_agents.core.prompting import Example, FewShotTemplate

tmpl = FewShotTemplate(
    instruction="Classify the sentiment of the following text as POSITIVE, NEGATIVE, or NEUTRAL.",
    examples=[
        Example(input_text="I love this product!", output_text="POSITIVE"),
        Example(input_text="This is terrible.", output_text="NEGATIVE"),
        Example(input_text="The package arrived today.", output_text="NEUTRAL"),
    ],
    input_label="Text",
    output_label="Sentiment",
)

prompt = tmpl.format(query="The documentation could be clearer but the API is solid.")
print(prompt)
```

**Dynamic example selection for a large pool:**

```python
from llm_agents.core.prompting import Example, ExampleSelector, FewShotTemplate

all_examples = [Example(input_text=q, output_text=a) for q, a in qa_dataset]

def word_overlap_scorer(query: str, example: Example) -> float:
    query_words = set(query.lower().split())
    example_words = set(example.input_text.lower().split())
    if not query_words:
        return 0.0
    return len(query_words & example_words) / len(query_words)

selector = ExampleSelector(examples=all_examples, scorer=word_overlap_scorer, top_k=3)

query = "How do I handle async exceptions in Python?"
selected = selector.select(query)

few_shot_tmpl = FewShotTemplate(
    instruction="Answer the Python question based on the examples below.",
    examples=selected,
)
prompt = few_shot_tmpl.format(query=query)
```
