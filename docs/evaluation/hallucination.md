# evaluation/hallucination

## Overview

The `evaluation/hallucination` module provides hallucination detection: given a generated answer and a set of reference passages, it computes a groundedness score and identifies which sentences in the answer are not supported by the evidence. The module exists because LLMs frequently produce fluent, plausible-sounding text that is factually unsupported by the retrieved context in a RAG system or the provided reference material. Detecting such hallucinations programmatically is critical for trust and safety in any production agent deployment. The module offers two detector implementations: a lightweight word-overlap heuristic (`OverlapDetector`) that requires no model dependencies and runs in pure Python, and a pluggable LLM-as-judge detector (`LLMJudgeDetector`) that delegates scoring to a caller-supplied callable — enabling integration with any external grounding model or API.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `HallucinationReport` | dataclass | Result of a detection run: groundedness score, flag, and unsupported spans. |
| `HallucinationDetector` | Protocol | Structural interface for hallucination detector implementations. |
| `OverlapDetector` | class | Token-overlap recall heuristic; no model dependencies. |
| `LLMJudgeDetector` | class | Delegates scoring to a caller-supplied `(answer, references) -> float` callable. |

### HallucinationReport

```
HallucinationReport(
    answer: str,
    groundedness_score: float,       # [0.0, 1.0]; 1.0 = fully grounded
    is_hallucination: bool,          # True when groundedness_score < threshold
    unsupported_spans: list[str],    # sentences flagged as unsupported
    metadata: dict[str, Any],        # detector diagnostics
)
```

### HallucinationDetector Protocol

```
detect(
    answer: str,
    references: list[str],
) -> HallucinationReport
```

Any object with a matching `detect` method satisfies this protocol without inheriting (`@runtime_checkable`).

### OverlapDetector

```
OverlapDetector(
    threshold: float = 0.5,           # groundedness below which is_hallucination=True
    sentence_threshold: float = 0.3,  # per-sentence recall below which span is flagged
)

detect(answer: str, references: list[str]) -> HallucinationReport
```

Splits `answer` into sentences using punctuation-based regex, computes token recall of each sentence against all references, averages sentence scores into an overall groundedness score.

### LLMJudgeDetector

```
LLMJudgeDetector(
    scorer: Callable[[str, list[str]], float],
    threshold: float = 0.5,
)

detect(answer: str, references: list[str]) -> HallucinationReport
```

Calls `scorer(answer, references)`, clamps the result to `[0.0, 1.0]`, and returns a `HallucinationReport`. Does not populate `unsupported_spans` (empty list); the scorer is responsible for any internal span analysis.

---

## Architecture

### Conceptual view

```
              answer + references
                      |
                      v
          HallucinationDetector (Protocol)
             /                    \
     OverlapDetector         LLMJudgeDetector
          |                         |
   split sentences            caller scorer
   per-sentence recall        (answer, refs) -> float
   mean groundedness          clamp to [0.0, 1.0]
          |                         |
          +----------+--------------+
                     |
              HallucinationReport
              (score, flag, spans)
```

### Data flow — OverlapDetector

1. `detect(answer, references)` is called with the generated text and a list of ground-truth or retrieved passages.
2. `_split_sentences(answer)` splits on `(?<=[.!?])\s+` (lookbehind at sentence-ending punctuation), filtering empty strings.
3. If the answer contains no sentences, a `HallucinationReport` with `groundedness_score=0.0` and `is_hallucination=True` is returned immediately.
4. For each sentence, `_sentence_recall(sentence, references)` is called. This computes `_recall(sentence, ref)` for each reference — the fraction of sentence tokens that appear in the reference token set — and returns the maximum across all references.
5. `_recall(candidate, reference)` tokenises with `re.findall(r"\w+", text.lower())`, converts to sets, and returns `|cand ∩ ref| / |cand|` (token precision of candidate against reference). If candidate is empty, returns 1.0; if candidate is non-empty but reference is empty, returns 0.0.
6. Sentences with recall below `sentence_threshold` are collected into `unsupported_spans`.
7. `groundedness = mean(sentence_scores)`. `is_hallucination = groundedness < threshold`.
8. `metadata` includes `"method": "overlap"` and `"sentence_scores"` for diagnostics.

### Data flow — LLMJudgeDetector

1. `detect(answer, references)` calls `self._scorer(answer, references)` and converts the result to float.
2. The score is clamped to `[0.0, 1.0]` via `max(0.0, min(1.0, score))`.
3. A `HallucinationReport` is returned with empty `unsupported_spans` and `metadata={"method": "llm_judge"}`.

### Key abstractions

**HallucinationDetector Protocol** is structural and `@runtime_checkable`. This means `isinstance(obj, HallucinationDetector)` works at runtime without requiring explicit class registration, and custom detectors need no imports from this module.

**HallucinationReport** captures both the scalar groundedness score and the identified unsupported spans in a single object. This dual representation serves two audiences: automated pipelines that threshold on `groundedness_score` or `is_hallucination`, and human reviewers who inspect `unsupported_spans` to understand what the model fabricated.

**Token recall as groundedness**: the `OverlapDetector` uses recall (what fraction of the answer's tokens appear in the references) rather than precision or F1. Recall measures whether the generated content is supported by the evidence; precision would measure whether the evidence contains the answer (less useful for hallucination detection). The word "recall" in the implementation's `_recall` function follows this convention: it measures how much of the candidate sentence is covered by the reference.

---

## Design decisions and tradeoffs

- **Decision**: `OverlapDetector` uses token-level set overlap (unigrams) rather than n-grams or embeddings. **Why**: Unigram overlap requires no external models or vector stores, runs in microseconds per sentence, and is deterministic and reproducible. **Tradeoff**: It is insensitive to word order, cannot detect factual errors that use correct vocabulary in wrong combinations (e.g., "Paris is the capital of Germany"), and is fooled by stopword-heavy text.

- **Decision**: Sentence splitting uses a simple lookbehind regex rather than a natural language sentence tokeniser. **Why**: Avoids adding `nltk` or `spacy` as a dependency for a module that is intended to be import-friendly without extras. **Tradeoff**: Sentences containing abbreviations with periods (e.g., "Dr. Smith") will be split incorrectly, producing spurious short fragments that may score poorly.

- **Decision**: `LLMJudgeDetector` does not populate `unsupported_spans`. **Why**: An LLM judge typically returns a single scalar score; decomposing it into sentence-level attributions would require a second API call or a more complex prompt. The current design keeps the integration point simple. **Tradeoff**: Callers using `LLMJudgeDetector` lose the span-level explainability that `OverlapDetector` provides.

- **Decision**: The score from `LLMJudgeDetector` is clamped to `[0.0, 1.0]`. **Why**: External scorers may return values slightly outside this range due to floating-point arithmetic or miscalibration. Clamping prevents downstream consumers from receiving scores they do not expect. **Tradeoff**: Clamping silently hides miscalibrated scorers; a better design would log a warning when clamping occurs.

- **Decision**: `_recall` returns 1.0 when both candidate and reference are empty, and 0.0 when candidate is non-empty but reference is empty. **Why**: An empty answer against an empty reference can be considered trivially supported. A non-empty answer against an empty reference has nothing to be supported by. **Tradeoff**: These edge-case behaviours may be surprising in practice; the empty-answer case is already handled separately by returning `groundedness_score=0.0` immediately.

---

## Scaling concerns

`OverlapDetector` runs in O(S * R * T) time where S is the number of sentences, R is the number of references, and T is the mean token count per sentence. For typical RAG use cases (5-20 references of ~100 tokens each, answers of 5-20 sentences), this is microseconds per call and scales well. The set-based tokenisation and intersection are efficient Python operations.

`LLMJudgeDetector` is bounded by its external scorer. If the scorer is a remote LLM API call, latency is typically 500 ms to several seconds per `detect` call. Batch detection is not supported.

Memory: `OverlapDetector` stores sentence scores and spans in-memory per call with no persistent state. `LLMJudgeDetector` holds a reference to the scorer callable only.

**What breaks first**: `LLMJudgeDetector` throughput under high-volume detection workloads. `OverlapDetector` scales comfortably to thousands of calls per second.

---

## Future improvements

- **Sentence tokeniser**: replace the regex splitter with a robust sentence tokeniser (e.g., PunktSentenceTokenizer from `nltk`) behind an optional extra to handle abbreviations and edge cases correctly.
- **N-gram and embedding overlap**: add `NGramOverlapDetector` and `EmbeddingOverlapDetector` implementations that use BM25 or cosine similarity to detect paraphrase-level hallucinations that unigram overlap misses.
- **Span attribution for LLMJudgeDetector**: add an optional `attribution_fn` argument to `LLMJudgeDetector` that, when provided, is called to populate `unsupported_spans` alongside the score.
- **Batch detection**: add an async `detect_batch(answers, references)` method to both detectors to allow amortizing LLM API call overhead across multiple answers.
- **Calibration utilities**: add tooling to calibrate detector thresholds against a labelled dataset of (answer, references, hallucination_label) triples.

---

## Usage examples

Using the overlap detector in a RAG response validation pipeline:

```python
from llm_agents.evaluation.hallucination import OverlapDetector

detector = OverlapDetector(threshold=0.5, sentence_threshold=0.3)
references = [
    "Paris is the capital city of France.",
    "The Eiffel Tower is located in Paris.",
]
answer = "Paris is the capital of France. It is located in Germany."

report = detector.detect(answer, references)
print(report.groundedness_score)      # e.g. 0.6
print(report.is_hallucination)        # True or False
print(report.unsupported_spans)       # ["It is located in Germany."]
```

Using an LLM judge scorer:

```python
from llm_agents.evaluation.hallucination import LLMJudgeDetector

def my_llm_scorer(answer: str, references: list[str]) -> float:
    # call your grounding model here
    return 0.85

detector = LLMJudgeDetector(scorer=my_llm_scorer, threshold=0.7)
report = detector.detect(answer="The sky is blue.", references=["The sky appears blue."])
print(report.is_hallucination)   # False (0.85 >= 0.7)
```

Checking the protocol at runtime:

```python
from llm_agents.evaluation.hallucination import HallucinationDetector, OverlapDetector

d = OverlapDetector()
print(isinstance(d, HallucinationDetector))  # True
```
