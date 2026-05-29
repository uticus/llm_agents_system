"""Tokenizer protocol and default approximation.

The ``Tokenizer`` protocol is a pluggable interface so callers can inject an
exact tokenizer (tiktoken, HuggingFace tokenizer, etc.) without touching the
rest of the long-context utilities.  The default approximation uses
``ceil(len(text) / 4)`` — 4 characters ≈ 1 token for English text.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable


@runtime_checkable
class Tokenizer(Protocol):
    """Protocol for token counting backends.

    Any callable object with a ``count(text)`` method satisfies this protocol
    without explicit inheritance.
    """

    def count(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        ...


class CharApproxTokenizer:
    """Default tokenizer: ``ceil(len(text) / 4)``, minimum 1.

    Suitable for planning and budgeting; not guaranteed to match any specific
    model's actual tokenization.
    """

    def count(self, text: str) -> int:  # noqa: PLR6301
        """Estimate token count for *text*."""
        return max(1, math.ceil(len(text) / 4))


_DEFAULT_TOKENIZER = CharApproxTokenizer()


def count_tokens(text: str, tokenizer: Tokenizer | None = None) -> int:
    """Count tokens in *text*.

    Args:
        text:      Input text.
        tokenizer: Optional :class:`Tokenizer`.  Defaults to
                   :class:`CharApproxTokenizer` when ``None``.

    Returns:
        Estimated token count (always >= 1 for non-empty text, 0 for empty).
    """
    if not text:
        return 0
    t = tokenizer if tokenizer is not None else _DEFAULT_TOKENIZER
    return t.count(text)
