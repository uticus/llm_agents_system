# long_context

## Overview

The `long_context` module provides utilities for handling text that exceeds a model's context window. It addresses three related problems: counting tokens in a model-agnostic way, splitting large texts into budget-respecting chunks at word boundaries, and asynchronously summarizing those chunks via the inference routing layer. The module exists because every other part of the system that works with unbounded text (memory, RAG, tool outputs, document ingestion) needs a single consistent answer to "does this fit in the window, and if not, what do I do?" It provides a pluggable `Tokenizer` protocol so teams can inject an exact model tokenizer (tiktoken, HuggingFace fast tokenizers) while falling back to a zero-dependency character approximation for planning and budget estimation.

---

## Public API

| Name | Kind | Description |
|---|---|---|
| `Tokenizer` | Protocol | Interface for token-counting backends. |
| `CharApproxTokenizer` | class | Default tokenizer using `ceil(len(text) / 4)`. |
| `count_tokens` | function | Count tokens in text, using a provided or default tokenizer. |
| `chunk` | function | Split text into chunks of at most `max_tokens` tokens each. |
| `pack_to_budget` | function | Greedily select a prefix of strings that fits within a token budget. |
| `Summarizer` | class | Async summarizer using map-reduce over chunks via an inference router. |

### `Tokenizer` (Protocol)

```python
@runtime_checkable
class Tokenizer(Protocol):
    def count(self, text: str) -> int: ...
```

Any object with a `count(text: str) -> int` method satisfies this protocol structurally.

### `CharApproxTokenizer`

```python
CharApproxTokenizer()
```

| Method | Signature | Description |
|---|---|---|
| `count` | `(text: str) -> int` | Returns `max(1, ceil(len(text) / 4))`. |

### `count_tokens`

```python
count_tokens(text: str, tokenizer: Tokenizer | None = None) -> int
```

Returns `0` for empty text. Uses `CharApproxTokenizer` when `tokenizer` is `None`.

### `chunk`

```python
chunk(text: str, max_tokens: int, tokenizer: Tokenizer | None = None) -> list[str]
```

Raises `ValueError` if `max_tokens <= 0`. Returns `[]` for empty/whitespace-only input. A single word that exceeds `max_tokens` is emitted as its own chunk rather than being dropped or truncated.

### `pack_to_budget`

```python
pack_to_budget(items: list[str], budget: int, tokenizer: Tokenizer | None = None) -> list[str]
```

Greedily accepts items left-to-right. Stops at the first item that would push the total over `budget`. Later items are not considered — this is a prefix selection, not a knapsack.

### `Summarizer`

```python
Summarizer(
    router: Router,
    model: str,
    max_chunk_tokens: int = 1000,
    tokenizer: Tokenizer | None = None,
)
```

| Method | Signature | Description |
|---|---|---|
| `summarize` | `async (text: str) -> str` | Chunk text and summarize each chunk; return joined summaries. |

Returns `""` for empty or whitespace-only input. Each chunk is sent as a separate `LLMRequest` with a fixed `_SUMMARY_PROMPT` prefix.

---

## Architecture

### Conceptual view

```
             caller
               |
    +----------+----------+
    |          |          |
 count_tokens  chunk   pack_to_budget
               |
          Tokenizer (Protocol)
          /         \
CharApproxTokenizer   <injected exact tokenizer>

    +----------------------------+
    |          Summarizer        |
    |   chunk() -> LLMRequest[]  |
    |         -> Router          |
    |         -> str[]           |
    |         -> join("\n")      |
    +----------------------------+
```

The tokenizer layer is shared by all three utilities. `Summarizer` depends on `chunk` and, through the router, on the inference routing layer. The chunking and packing functions are pure (no I/O), while `Summarizer.summarize` is an async coroutine.

### Data flow

**Chunking path:**

1. Caller provides raw text and a `max_tokens` limit.
2. `chunk` splits text into words using `str.split()`.
3. For each word, a candidate chunk is formed by appending the word to the current accumulator.
4. If `count_tokens(candidate)` exceeds `max_tokens` and there are accumulated words, the current accumulator is flushed as a chunk and a new accumulator is started with the current word.
5. The final accumulator is flushed as the last chunk.
6. The result is a list of non-empty strings in original order.

**Summarization path:**

1. `Summarizer.summarize` calls `chunk(text, max_chunk_tokens, tokenizer)`.
2. For each chunk, it constructs an `LLMRequest` with `_SUMMARY_PROMPT + chunk_text` as the user message.
3. It awaits `router.complete(request)` sequentially (no concurrency currently).
4. Per-chunk summaries are joined with `"\n"` and returned.

**Packing path:**

1. `pack_to_budget` iterates items left-to-right.
2. For each item, it calls `count_tokens` to get the item's token count.
3. If adding the item would exceed `budget`, iteration stops.
4. Accepted items are collected and returned as a prefix list.

### Key abstractions

**`Tokenizer` (Protocol)** — decouples token counting from any specific model. The single-method contract (`count(text) -> int`) is intentionally minimal so that tiktoken, HuggingFace tokenizers, or any custom approximation can satisfy it. The `@runtime_checkable` decorator enables `isinstance` checks in tests and guard clauses.

**`CharApproxTokenizer`** — provides a zero-dependency default that works correctly enough for budget planning. The `ceil(len / 4)` formula is calibrated for English prose with typical GPT-family tokenization. The minimum of `1` prevents zero-cost entries from accumulating without limit.

**`chunk`** — the core utility that all context-window-sensitive code should use. The word-boundary splitting guarantees that chunks can be decoded as natural-language fragments (no mid-word cuts) and that outputs reassemble cleanly.

**`pack_to_budget`** — a complementary utility for scenarios where the input is already a list of independent items (retrieved memory snippets, tool result lines, few-shot examples) and the goal is to fit as many as possible into the remaining context budget.

**`Summarizer`** — implements the simplest viable summarization strategy: one LLM call per chunk, results concatenated. This is a "map" without a "reduce" pass, which means the output length is proportional to the number of chunks, not bounded. A future refine strategy is mentioned in the source comments but not yet implemented.

---

## Design decisions and tradeoffs

- **Decision**: Use a character-based approximation as the default tokenizer. **Why**: Eliminates the dependency on `tiktoken` or any model-specific tokenizer in the core layer. The core layer is meant to be model-agnostic. **Tradeoff**: Token counts are inaccurate for code, non-ASCII scripts, or very short tokens. Callers with strict budget requirements must inject an exact tokenizer.

- **Decision**: `chunk` splits at whitespace boundaries only. **Why**: Word-boundary splitting preserves semantic coherence and guarantees clean reassembly. Byte-level splitting would produce garbled fragments. **Tradeoff**: A single very long word (e.g. a base64 blob, a URL) will be emitted as an oversized chunk that exceeds `max_tokens`. This is documented and intentional — truncation would be worse.

- **Decision**: `pack_to_budget` is a greedy prefix selection, not a knapsack. **Why**: Knapsack is NP-hard in the general case. For most agent use cases, items are priority-ordered by the caller (e.g. most relevant first) so a greedy prefix gives the optimal result. **Tradeoff**: If a caller provides items in arbitrary order, the greedy approach may accept a large low-priority item and exclude many small high-priority items that would have fit.

- **Decision**: `Summarizer.summarize` is sequential, not concurrent. **Why**: Simplifies error handling and tracing. Concurrent chunk summarization would require managing partial failures, result ordering, and rate limits. **Tradeoff**: Summarizing a 100-chunk document requires 100 serial LLM calls, which is slow. For production use, concurrency with backpressure control is necessary.

- **Decision**: The summarization prompt is a module-level constant (`_SUMMARY_PROMPT`). **Why**: Keeps the constructor simple and avoids per-instance prompt management complexity. **Tradeoff**: Callers cannot customize the summarization instruction without subclassing or modifying the source. A `prompt_template` parameter would make this more flexible.

---

## Scaling concerns

- `chunk` is O(n) in text length and O(k) in chunk count per token-counting call, where each `count_tokens` call is O(len(candidate)) for the character approximation. Total complexity is O(n * avg_word_length), which is acceptable for documents up to a few MB.
- With an injected tiktoken tokenizer, `count_tokens` performs a full tokenization of the growing candidate string on each word addition, making `chunk` O(n^2) in the number of words per chunk. This is acceptable for chunk sizes up to a few thousand tokens but becomes slow for very large `max_tokens` values.
- `Summarizer.summarize` makes one LLM call per chunk. For a 100,000-token document with 1,000-token chunks, that is 100 sequential API calls. This hits rate limits on most providers and introduces significant latency.
- `pack_to_budget` is O(n) in items, acceptable for any realistic context-packing scenario.

---

## Future improvements

- **Concurrent summarization in `Summarizer`**: Dispatch all chunk summaries concurrently using `asyncio.gather` with a semaphore to control concurrency and avoid rate limit exhaustion.
- **Reduce pass in `Summarizer`**: After the map pass, apply a second summarization pass over the concatenated chunk summaries to produce a bounded-length final summary. This is the classic map-reduce summarization pattern.
- **Customizable summarization prompt**: Accept a `prompt_template: str` parameter in `Summarizer.__init__` so callers can provide domain-specific summarization instructions.
- **Efficient incremental chunking**: Cache partial token counts so that appending a word does not require re-tokenizing the entire candidate string. This would make chunking O(n) even with exact tokenizers.
- **Overlap support in `chunk`**: Add a `stride` parameter so adjacent chunks share a window of context, which improves retrieval and summarization quality for RAG pipelines.

---

## Usage examples

**Token counting with the default approximation:**

```python
from llm_agents.core.long_context import count_tokens

text = "The quick brown fox jumps over the lazy dog."
n = count_tokens(text)
print(n)  # approximately 11
```

**Chunking a large document:**

```python
from llm_agents.core.long_context import chunk

document = open("large_report.txt").read()
chunks = chunk(document, max_tokens=500)
print(f"Split into {len(chunks)} chunks")
for i, c in enumerate(chunks):
    print(f"Chunk {i}: {len(c.split())} words")
```

**Packing retrieved memory items into a context budget:**

```python
from llm_agents.core.long_context import pack_to_budget

# Items ordered by relevance score (most relevant first)
retrieved_items = [item.content for item in ltm.search("API key", limit=20)]
budget = 800  # tokens reserved for context

packed = pack_to_budget(retrieved_items, budget=budget)
context_block = "\n".join(packed)
```

**Summarizing a long document via the router:**

```python
from llm_agents.core.long_context import Summarizer

summarizer = Summarizer(router=router, model="gpt-4o-mini", max_chunk_tokens=1000)
summary = await summarizer.summarize(long_document_text)
print(summary)
```
