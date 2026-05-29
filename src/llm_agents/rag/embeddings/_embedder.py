"""Embedder protocol and FakeEmbedder implementation.

:class:`Embedder` is a structural ``Protocol`` — any class with a matching
``embed`` method qualifies.

:class:`FakeEmbedder` produces deterministic fixed-dimension vectors for
tests, with optional batch-size tracking.
"""

from __future__ import annotations

from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """Protocol for text embedding models.

    Any object with a matching ``embed`` method and ``dimensions`` attribute
    satisfies this interface without needing to inherit from :class:`Embedder`.
    """

    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for *texts*.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            List of float vectors, one per input text.  Each vector has
            ``self.dimensions`` elements.
        """
        ...


class FakeEmbedder:
    """Deterministic test embedder that produces constant unit vectors.

    Each text maps to a vector of ``dimensions`` floats where the first
    element is ``1.0 / sqrt(dimensions)`` and the rest are ``0.0``, making
    the vector a unit vector along the first axis.  This is predictable and
    independent of text content, which simplifies assertions in tests.

    Args:
        dimensions: Dimensionality of the output vectors.

    Attributes:
        embed_count: Number of ``embed`` calls made so far.
        total_texts: Total number of individual texts embedded.
    """

    def __init__(self, dimensions: int = 4) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be >= 1")
        self.dimensions = dimensions
        self.embed_count = 0
        self.total_texts = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a unit vector along the first axis for each text.

        Args:
            texts: List of strings.  May be empty; returns ``[]``.

        Returns:
            List of ``len(texts)`` vectors, each of length ``dimensions``.
        """
        self.embed_count += 1
        self.total_texts += len(texts)
        return [[1.0] + [0.0] * (self.dimensions - 1) for _ in texts]


class BatchEmbedder:
    """Wraps another :class:`Embedder` and batches calls by *batch_size*.

    Args:
        embedder:   Underlying embedder to call.
        batch_size: Maximum number of texts per underlying ``embed`` call.
    """

    def __init__(self, embedder: Any, batch_size: int = 32) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._embedder = embedder
        self.batch_size = batch_size

    @property
    def dimensions(self) -> int:
        return self._embedder.dimensions  # type: ignore[no-any-return]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* in batches of at most ``batch_size``.

        Args:
            texts: Texts to embed.

        Returns:
            Concatenated embedding list in original order.
        """
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            results.extend(self._embedder.embed(batch))
        return results
