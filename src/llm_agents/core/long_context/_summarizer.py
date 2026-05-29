"""Async summarization pipeline using map-reduce over chunks.

:class:`Summarizer` chunks a large text, sends each chunk to a model via the
inference-routing layer, and concatenates the chunk summaries into a single
compressed output.

This is intentionally simple: one pass of map (chunk → summary) with no
reduce step beyond concatenation.  A future ``refine`` strategy can be added
without changing the public interface.
"""

from __future__ import annotations

from llm_agents.core.long_context._chunking import chunk
from llm_agents.core.long_context._tokenizer import Tokenizer
from llm_agents.infra.inference_routing._models import LLMRequest
from llm_agents.infra.inference_routing._router import Router

_SUMMARY_PROMPT = (
    "Summarize the following text concisely, preserving key information:\n\n"
)


class Summarizer:
    """Async text summarizer backed by an inference :class:`Router`.

    Args:
        router:           Router to use for each summary call.
        model:            Model identifier passed in each :class:`LLMRequest`.
        max_chunk_tokens: Each input chunk is limited to this many tokens.
                          Default 1000.
        tokenizer:        Optional tokenizer used for chunking.
    """

    def __init__(
        self,
        router: Router,
        model: str,
        max_chunk_tokens: int = 1000,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        self._router = router
        self._model = model
        self._max_chunk_tokens = max_chunk_tokens
        self._tokenizer = tokenizer

    async def summarize(self, text: str) -> str:
        """Summarize *text* by chunking and then summarizing each chunk.

        Args:
            text: Input text to summarize.

        Returns:
            Concatenation of per-chunk summaries, separated by a newline.
            Returns an empty string for empty input.
        """
        if not text.strip():
            return ""

        chunks = chunk(text, self._max_chunk_tokens, self._tokenizer)
        if not chunks:
            return ""

        summaries: list[str] = []
        for chunk_text in chunks:
            prompt = _SUMMARY_PROMPT + chunk_text
            request = LLMRequest(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            response = await self._router.complete(request)
            summaries.append(response.content)

        return "\n".join(summaries)
