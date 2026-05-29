"""Deterministic text chunking and budget-aware packing.

``chunk()`` splits text at word boundaries so that each chunk contains at most
``max_tokens`` tokens.  The output is deterministic: the same input with the
same tokenizer and the same ``max_tokens`` always produces the same chunks.

``pack_to_budget()`` greedily selects a prefix of a list of strings that fits
within a token budget, stopping before the first item that would push the total
over the limit.
"""

from __future__ import annotations

from llm_agents.core.long_context._tokenizer import Tokenizer, count_tokens


def chunk(
    text: str,
    max_tokens: int,
    tokenizer: Tokenizer | None = None,
) -> list[str]:
    """Split *text* into chunks of at most *max_tokens* tokens each.

    Splitting is done at whitespace boundaries (words).  A single word that
    exceeds *max_tokens* is kept as its own chunk rather than being truncated.

    Args:
        text:       Input text to chunk.
        max_tokens: Maximum token count per chunk (must be > 0).
        tokenizer:  Optional tokenizer; defaults to :class:`CharApproxTokenizer`.

    Returns:
        List of non-empty string chunks in original order.  Returns ``[]``
        when *text* is empty.
    """
    if not text.strip():
        return []
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be > 0, got {max_tokens}")

    words = text.split()
    chunks: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate_words = current_words + [word]
        candidate_text = " ".join(candidate_words)
        candidate_tokens = count_tokens(candidate_text, tokenizer)
        if current_words and candidate_tokens > max_tokens:
            # Flush current chunk; start a new one with this word.
            chunks.append(" ".join(current_words))
            current_words = [word]
        else:
            current_words = candidate_words

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def pack_to_budget(
    items: list[str],
    budget: int,
    tokenizer: Tokenizer | None = None,
) -> list[str]:
    """Greedily pack *items* into a token budget.

    Items are accepted in left-to-right order until the next item would push
    the total token count over *budget*.  Packing stops at that point — later
    items are not considered.

    Args:
        items:     Ordered list of strings to pack.
        budget:    Maximum total token count to include.
        tokenizer: Optional tokenizer; defaults to :class:`CharApproxTokenizer`.

    Returns:
        The largest prefix of *items* that fits within *budget*.  May be empty
        if the first item alone exceeds the budget.
    """
    result: list[str] = []
    total: int = 0
    for item in items:
        tokens = count_tokens(item, tokenizer)
        if total + tokens > budget:
            break
        result.append(item)
        total += tokens
    return result
