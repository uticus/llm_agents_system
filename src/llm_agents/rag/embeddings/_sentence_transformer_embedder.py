"""SentenceTransformerEmbedder: local text embedding via sentence-transformers.

Requires the ``rag`` optional extra (``sentence-transformers`` package).
The package is imported lazily on first use so this module is importable
without it installed.
"""

from __future__ import annotations


class SentenceTransformerEmbedder:
    """Embedder backed by a ``sentence_transformers.SentenceTransformer`` model.

    The underlying model is loaded lazily on the first call to :meth:`embed`
    or on the first read of :attr:`dimensions`, so importing this module does
    not require ``sentence-transformers`` to be installed.

    Args:
        model_name: HuggingFace model identifier or local path.
            Defaults to ``"all-MiniLM-L6-v2"``.
        device: Torch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
            Defaults to ``"cpu"``.
        normalize_embeddings: When ``True`` (default) vectors are L2-normalised
            by the model so cosine similarity equals dot product.

    Attributes:
        model_name: The model identifier passed at construction.
        device: The device string passed at construction.
        normalize_embeddings: Whether L2-normalisation is applied.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        device: str = "cpu",
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self._model = None
        self._dimensions: int | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Return the loaded ``SentenceTransformer`` model, loading it on demand.

        Raises:
            ImportError: If ``sentence-transformers`` is not installed.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for SentenceTransformerEmbedder. "
                    "Install it with: pip install 'llm-agents-system[rag]'"
                ) from exc
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    # ------------------------------------------------------------------
    # Embedder protocol
    # ------------------------------------------------------------------

    @property
    def dimensions(self) -> int:
        """Dimensionality of the model's output vectors.

        Loads the model on first access if it has not been loaded yet.

        Returns:
            Number of floats in each embedding vector.
        """
        if self._dimensions is None:
            self._dimensions = int(self._get_model().get_sentence_embedding_dimension())
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed *texts* using the sentence-transformer model.

        The model is loaded on the first call.  Subsequent calls reuse the
        already-loaded model.

        Args:
            texts: List of strings to embed.  Returns ``[]`` for empty input.

        Returns:
            List of float vectors, one per input text.  Each vector has
            ``self.dimensions`` elements.
        """
        if not texts:
            return []
        model = self._get_model()
        raw = model.encode(
            texts,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        result: list[list[float]] = [row.tolist() for row in raw]
        if self._dimensions is None and result:
            self._dimensions = len(result[0])
        return result
