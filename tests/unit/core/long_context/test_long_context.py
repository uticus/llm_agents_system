"""Unit tests for core/long_context.

Covers token counting, chunking, packing, and summarization.
No real network calls.
"""

from __future__ import annotations

import asyncio
import math

import pytest

from llm_agents.core.long_context import (
    CharApproxTokenizer,
    Summarizer,
    Tokenizer,
    chunk,
    count_tokens,
    pack_to_budget,
)
from llm_agents.infra.inference_routing import (
    Candidate,
    FakeProvider,
    LLMResponse,
    Router,
    RoutingPolicy,
)
from llm_agents.infra.tracing import get_collector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_router(content: str = "summary") -> Router:
    """Build a Router that always returns a response with the given content."""
    resp = LLMResponse(
        model="m",
        content=content,
        prompt_tokens=10,
        completion_tokens=5,
        latency_s=0.01,
    )
    provider = FakeProvider("p", [resp] * 100)
    policy = RoutingPolicy(
        candidates=[Candidate(provider=provider, model="m")],
        max_retries=0,
    )
    return Router(policy=policy, export_hook=None)


@pytest.fixture(autouse=True)
def reset_collector():
    get_collector().reset()
    yield
    get_collector().reset()


# ---------------------------------------------------------------------------
# T1 — count_tokens: default approximation
# ---------------------------------------------------------------------------


def test_count_tokens_default_approximation():
    """T1a: Default tokenizer uses ceil(len(text)/4)."""
    text = "Hello world"
    expected = math.ceil(len(text) / 4)
    assert count_tokens(text) == expected


def test_count_tokens_empty_string():
    """T1b: Empty string returns 0."""
    assert count_tokens("") == 0


# ---------------------------------------------------------------------------
# T2 — count_tokens: custom tokenizer
# ---------------------------------------------------------------------------


def test_count_tokens_custom_tokenizer():
    """T2: Custom tokenizer is used when provided."""

    class WordTokenizer:
        def count(self, text: str) -> int:
            return len(text.split())

    assert count_tokens("hello world foo", tokenizer=WordTokenizer()) == 3


def test_tokenizer_protocol_satisfied_by_char_approx():
    """T2b: CharApproxTokenizer satisfies Tokenizer protocol."""
    t = CharApproxTokenizer()
    assert isinstance(t, Tokenizer)


# ---------------------------------------------------------------------------
# T3 — chunk: deterministic
# ---------------------------------------------------------------------------


def test_chunk_deterministic():
    """T3: Same input always produces same output."""
    text = "The quick brown fox jumped over the lazy dog"
    out1 = chunk(text, max_tokens=5)
    out2 = chunk(text, max_tokens=5)
    assert out1 == out2


def test_chunk_same_content_joined():
    """T3b: Joining all chunks reproduces the original (whitespace-normalized)."""
    text = "  alpha beta   gamma delta  epsilon  "
    chunks = chunk(text, max_tokens=10)
    joined = " ".join(chunks)
    assert joined == " ".join(text.split())


# ---------------------------------------------------------------------------
# T4 — chunk: each chunk respects max_tokens
# ---------------------------------------------------------------------------


def test_chunk_each_chunk_within_max_tokens():
    """T4: Every chunk has token_count <= max_tokens (except single oversize words)."""
    text = "word " * 50
    max_t = 8
    for ch in chunk(text, max_tokens=max_t):
        assert count_tokens(ch) <= max_t


def test_chunk_large_single_word_kept():
    """T4b: A single word that exceeds max_tokens is kept as its own chunk."""
    long_word = "a" * 100  # 100 chars → ceil(100/4) = 25 tokens
    chunks = chunk(long_word, max_tokens=5)
    assert len(chunks) == 1
    assert chunks[0] == long_word


# ---------------------------------------------------------------------------
# T5 — chunk: empty input
# ---------------------------------------------------------------------------


def test_chunk_empty_string():
    """T5a: Empty string returns []."""
    assert chunk("", max_tokens=10) == []


def test_chunk_whitespace_only():
    """T5b: Whitespace-only string returns []."""
    assert chunk("   \n\t  ", max_tokens=10) == []


def test_chunk_invalid_max_tokens():
    """T5c: max_tokens <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="max_tokens"):
        chunk("hello", max_tokens=0)


# ---------------------------------------------------------------------------
# T6 — pack_to_budget
# ---------------------------------------------------------------------------


def test_pack_to_budget_fits_items():
    """T6: Items fitting within budget are all included."""
    items = ["ab", "cd", "ef"]  # each ~1 token
    result = pack_to_budget(items, budget=10)
    assert result == items


def test_pack_to_budget_stops_at_limit():
    """T6b: Stops before the first item that would exceed budget."""
    # "abcd" = ceil(4/4) = 1 token each; budget = 2 → include 2 items
    items = ["abcd", "abcd", "abcd", "abcd"]
    result = pack_to_budget(items, budget=2)
    assert len(result) == 2


def test_pack_to_budget_empty_input():
    """T6c: Empty input returns []."""
    assert pack_to_budget([], budget=100) == []


# ---------------------------------------------------------------------------
# T7 — pack_to_budget: single item
# ---------------------------------------------------------------------------


def test_pack_to_budget_single_item_fits():
    """T7a: Single item within budget is included."""
    result = pack_to_budget(["hello"], budget=100)
    assert result == ["hello"]


def test_pack_to_budget_single_item_exceeds():
    """T7b: Single item exceeding budget is excluded; empty list returned."""
    big = "a" * 200  # ceil(200/4) = 50 tokens
    result = pack_to_budget([big], budget=10)
    assert result == []


# ---------------------------------------------------------------------------
# T8 — Summarizer: one call per chunk
# ---------------------------------------------------------------------------


def test_summarizer_one_call_per_chunk():
    """T8: Summarizer dispatches one router call per chunk."""
    # Craft text so it makes exactly 2 chunks with small max_chunk_tokens
    # Each word is 4 chars = 1 token; max_chunk_tokens=4 → 4 words per chunk
    text = " ".join(["word"] * 10)  # 10 words → should produce 3 chunks at 4 tokens each
    resp = LLMResponse(
        model="m", content="chunksum", prompt_tokens=5, completion_tokens=3, latency_s=0.01
    )
    provider = FakeProvider("p", [resp] * 10)
    policy = RoutingPolicy(
        candidates=[Candidate(provider=provider, model="m")],
        max_retries=0,
    )
    router = Router(policy=policy, export_hook=None)
    summarizer = Summarizer(router, model="m", max_chunk_tokens=4)
    result = asyncio.run(summarizer.summarize(text))

    expected_chunks = chunk(text, max_tokens=4)
    assert provider.call_count == len(expected_chunks)
    assert result.count("chunksum") == len(expected_chunks)


def test_summarizer_concatenates_results():
    """T8b: Chunk summaries are joined with newline."""
    # Force 2 chunks
    text = " ".join(["word"] * 8)
    r1 = LLMResponse(
        model="m", content="first", prompt_tokens=5, completion_tokens=2, latency_s=0.01
    )
    r2 = LLMResponse(
        model="m", content="second", prompt_tokens=5, completion_tokens=2, latency_s=0.01
    )
    provider = FakeProvider("p", [r1, r2])
    policy = RoutingPolicy(
        candidates=[Candidate(provider=provider, model="m")],
        max_retries=0,
    )
    router = Router(policy=policy, export_hook=None)
    summarizer = Summarizer(router, model="m", max_chunk_tokens=4)
    result = asyncio.run(summarizer.summarize(text))
    parts = result.split("\n")
    assert "first" in parts
    assert "second" in parts


# ---------------------------------------------------------------------------
# T9 — Summarizer: short text (single chunk)
# ---------------------------------------------------------------------------


def test_summarizer_short_text_single_chunk():
    """T9: Short text fits in one chunk; router called exactly once."""
    router = _fake_router("short summary")
    summarizer = Summarizer(router, model="m", max_chunk_tokens=1000)
    result = asyncio.run(summarizer.summarize("Hello world."))
    assert result == "short summary"


def test_summarizer_empty_text():
    """T9b: Empty text returns empty string without calling router."""
    router = _fake_router("should not appear")
    summarizer = Summarizer(router, model="m")
    result = asyncio.run(summarizer.summarize(""))
    assert result == ""
