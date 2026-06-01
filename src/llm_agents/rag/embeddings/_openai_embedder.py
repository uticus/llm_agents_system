"""OpenAIEmbedder: embeddings via the OpenAI embeddings API.

The caller injects an ``openai.OpenAI`` (or ``openai.AzureOpenAI``) client;
this module never imports ``openai`` directly.
"""

from __future__ import annotations


class OpenAIEmbedder:
    """Embedder backed by the OpenAI embeddings API.

    The client is injected by the caller so this module never imports
    ``openai``.  Any object that exposes
    ``client.embeddings.create(model=..., input=..., **kwargs)`` and returns
    a response with a ``.data`` iterable of objects that have an
    ``.embedding`` attribute is accepted.

    Args:
        client:     OpenAI-compatible client (e.g. ``openai.OpenAI()``,
                    ``openai.AzureOpenAI()``).
        model:      Embeddings model name.  Defaults to
                    ``"text-embedding-3-small"``.
        dimensions: Output vector dimensionality.  When provided it is
                    forwarded to the API as the ``dimensions`` parameter
                    (supported by ``text-embedding-3-*`` models for
                    Matryoshka-style dimensionality reduction) and
                    :attr:`dimensions` is available immediately.  When
                    omitted :attr:`dimensions` is inferred from the first API
                    response and raises ``ValueError`` if read before then.

    Attributes:
        model: The model name passed at construction.
    """

    def __init__(
        self,
        client,
        model: str = "text-embedding-3-small",
        *,
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self._dimensions = dimensions

    # ------------------------------------------------------------------
    # Embedder protocol
    # ------------------------------------------------------------------

    @property
    def dimensions(self) -> int:
        """Dimensionality of the output vectors.

        Returns:
            Number of floats in each embedding vector.

        Raises:
            ValueError: If :attr:`dimensions` was not supplied at construction
                and no :meth:`embed` call has been made yet.
        """
        if self._dimensions is None:
            raise ValueError(
                "OpenAIEmbedder.dimensions is not known yet. "
                "Either pass dimensions= in the constructor or call embed() first."
            )
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* via a single OpenAI embeddings API call.

        Args:
            texts: List of strings to embed.  Returns ``[]`` for empty input.

        Returns:
            List of float vectors, one per input text, in the same order.
            Each vector has ``self.dimensions`` elements after the call.
        """
        if not texts:
            return []
        kwargs: dict = {}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        response = self._client.embeddings.create(
            model=self.model,
            input=texts,
            **kwargs,
        )
        result: list[list[float]] = [list(item.embedding) for item in response.data]
        if self._dimensions is None and result:
            self._dimensions = len(result[0])
        return result
