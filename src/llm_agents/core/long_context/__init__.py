"""Long-context handling: token counting, chunking, packing, and summarization.

Public surface
--------------
Token counting::

    from llm_agents.core.long_context import count_tokens, Tokenizer

Chunking and packing::

    from llm_agents.core.long_context import chunk, pack_to_budget

Summarization::

    from llm_agents.core.long_context import Summarizer

    summarizer = Summarizer(router, model="gpt-4o")
    summary = await summarizer.summarize(long_text)
"""

from llm_agents.core.long_context._chunking import chunk, pack_to_budget
from llm_agents.core.long_context._summarizer import Summarizer
from llm_agents.core.long_context._tokenizer import CharApproxTokenizer, Tokenizer, count_tokens

__all__ = [
    "CharApproxTokenizer",
    "Summarizer",
    "Tokenizer",
    "chunk",
    "count_tokens",
    "pack_to_budget",
]
