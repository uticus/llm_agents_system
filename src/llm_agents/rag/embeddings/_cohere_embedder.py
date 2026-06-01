"""CohereEmbedder: embeddings via the Cohere embeddings API.

The caller injects a ``cohere.Client`` (or ``cohere.ClientV2``) instance;
this module never imports ``cohere`` directly.
"""

from __future__ import annotations


class CohereEmbedder:
    """Embedder backed by the Cohere embeddings API.

    The client is injected by the caller so this module never imports
    ``cohere``.  Any object that exposes
    ``client.embed(texts=..., model=..., input_type=...)`` and returns a
    response whose ``.embeddings`` attribute is a list of float vectors is
    accepted.

    Args:
        client:     Cohere client instance (e.g. ``cohere.Client(api_key)``).
        model:      Cohere embeddings model name.  Defaults to
                    ``"embed-english-v3.0"``.
        input_type: Cohere input-type hint.  Required by v3+ models; controls
                    how the model interprets the texts.  One of
                    ``"search_document"`` (default), ``"search_query"``,
                    ``"classification"``, or ``"clustering"``.
        dimensions: Output vector dimensionality.  When provided it is stored
                    immediately and used to validate responses.  When omitted
                    :attr:`dimensions` is inferred from the first API response
                    and raises ``ValueError`` if read before then.

    Attributes:
        model:      The model name passed at construction.
        input_type: The input-type hint forwarded to the API on every call.
    """

    def __init__(
        self,
        client,
        model: str = "embed-english-v3.0",
        *,
        input_type: str = "search_document",
        dimensions: int | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.input_type = input_type
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
                "CohereEmbedder.dimensions is not known yet. "
                "Either pass dimensions= in the constructor or call embed() first."
            )
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* via a single Cohere embeddings API call.

        Args:
            texts: List of strings to embed.  Returns ``[]`` for empty input.

        Returns:
            List of float vectors, one per input text, in the same order.
            Each vector has ``self.dimensions`` elements after the call.
        """
        if not texts:
            return []
        response = self._client.embed(
            texts=texts,
            model=self.model,
            input_type=self.input_type,
        )
        result: list[list[float]] = [list(vec) for vec in response.embeddings]
        if self._dimensions is None and result:
            self._dimensions = len(result[0])
        return result
