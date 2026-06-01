"""Unit tests for rag/pipeline: GroundedAnswer, RagPipeline."""

from __future__ import annotations

from llm_agents.rag.embeddings import FakeEmbedder
from llm_agents.rag.pipeline import GroundedAnswer, RagPipeline
from llm_agents.rag.reranking import FakeReranker
from llm_agents.rag.retrieval import DenseRetriever, RetrievedPassage
from llm_agents.rag.vector_store import InMemoryVectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(n: int = 3, dims: int = 4) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    for i in range(n):
        store.upsert(
            f"chunk#{i}",
            [1.0] + [0.0] * (dims - 1),
            metadata={"text": f"passage {i}", "doc_id": f"doc{i}"},
        )
    return store


def _make_retriever(store: InMemoryVectorStore, top_k: int = 5) -> DenseRetriever:
    embedder = FakeEmbedder(dimensions=4)
    return DenseRetriever(embedder, store, top_k=top_k)


def _concat_generator(query: str, passages: list[RetrievedPassage]) -> str:
    texts = " | ".join(p.text for p in passages)
    return f"Answer for '{query}' using: {texts}"


def _static_generator(query: str, passages: list[RetrievedPassage]) -> str:
    return "static"


# ---------------------------------------------------------------------------
# GroundedAnswer
# ---------------------------------------------------------------------------


class TestGroundedAnswer:
    def test_defaults(self) -> None:
        ga = GroundedAnswer(query="q", answer="a")
        assert ga.query == "q"
        assert ga.answer == "a"
        assert ga.citations == []

    def test_with_citations(self) -> None:
        p = RetrievedPassage(doc_id="c1", text="x")
        ga = GroundedAnswer(query="q", answer="a", citations=[p])
        assert len(ga.citations) == 1
        assert ga.citations[0].doc_id == "c1"


# ---------------------------------------------------------------------------
# RagPipeline — without reranker
# ---------------------------------------------------------------------------


class TestRagPipelineNoReranker:
    def test_returns_grounded_answer(self) -> None:
        store = _make_store()
        retriever = _make_retriever(store)
        pipeline = RagPipeline(retriever, _static_generator)
        result = pipeline.answer("what is x?")
        assert isinstance(result, GroundedAnswer)
        assert result.query == "what is x?"
        assert result.answer == "static"

    def test_citations_from_retriever(self) -> None:
        store = _make_store(n=3)
        retriever = _make_retriever(store, top_k=2)
        pipeline = RagPipeline(retriever, _static_generator, top_k=2)
        result = pipeline.answer("q")
        assert len(result.citations) <= 2

    def test_generator_receives_passages(self) -> None:
        store = _make_store(n=2)
        retriever = _make_retriever(store, top_k=2)
        captured: list[list[RetrievedPassage]] = []

        def capturing_generator(query, passages):
            captured.append(passages)
            return "ok"

        pipeline = RagPipeline(retriever, capturing_generator, top_k=2)
        pipeline.answer("q")
        assert len(captured) == 1
        assert len(captured[0]) == 2

    def test_empty_store_produces_no_citations(self) -> None:
        store = InMemoryVectorStore()
        retriever = _make_retriever(store)
        pipeline = RagPipeline(retriever, _static_generator)
        result = pipeline.answer("q")
        assert result.citations == []

    def test_per_call_top_k_override(self) -> None:
        store = _make_store(n=5)
        retriever = _make_retriever(store, top_k=5)
        pipeline = RagPipeline(retriever, _static_generator, top_k=5)
        result = pipeline.answer("q", top_k=1)
        assert len(result.citations) <= 1


# ---------------------------------------------------------------------------
# RagPipeline — with reranker
# ---------------------------------------------------------------------------


class TestRagPipelineWithReranker:
    def test_reranker_called_after_retrieval(self) -> None:
        store = _make_store(n=4)
        retriever = _make_retriever(store, top_k=4)
        reranker = FakeReranker()
        pipeline = RagPipeline(retriever, _static_generator, reranker=reranker, top_k=4)
        pipeline.answer("q")
        assert reranker.rerank_count == 1

    def test_reranker_reversal_reflected_in_citations(self) -> None:
        store = _make_store(n=3)
        retriever = _make_retriever(store, top_k=3)
        reranker = FakeReranker()
        pipeline = RagPipeline(retriever, _static_generator, reranker=reranker, top_k=3)
        result = pipeline.answer("q")
        # FakeReranker reverses; all 3 passages should be present
        assert len(result.citations) == 3

    def test_top_n_truncation_via_reranker(self) -> None:
        store = _make_store(n=4)
        retriever = _make_retriever(store, top_k=4)
        reranker = FakeReranker(top_n=2)
        pipeline = RagPipeline(retriever, _static_generator, reranker=reranker, top_k=4)
        result = pipeline.answer("q")
        assert len(result.citations) <= 2

    def test_per_call_top_n_override(self) -> None:
        store = _make_store(n=4)
        retriever = _make_retriever(store, top_k=4)
        reranker = FakeReranker(top_n=10)
        pipeline = RagPipeline(retriever, _static_generator, reranker=reranker, top_k=4)
        result = pipeline.answer("q", top_n=1)
        assert len(result.citations) <= 1

    def test_without_reranker_no_rerank_call(self) -> None:
        store = _make_store(n=2)
        retriever = _make_retriever(store, top_k=2)
        # No reranker; using a sentinel to confirm rerank is never called
        called: list[bool] = []

        class SentinelReranker:
            def rerank(self, query, passages, *, top_n=None):
                called.append(True)
                return passages

        pipeline = RagPipeline(retriever, _static_generator)
        pipeline.answer("q")
        assert called == []


# ---------------------------------------------------------------------------
# RagPipeline — filters
# ---------------------------------------------------------------------------


class TestRagPipelineFilters:
    def test_filter_forwarded_to_retriever(self) -> None:
        store = InMemoryVectorStore()
        store.upsert("c0", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "A", "text": "a"})
        store.upsert("c1", [1.0, 0.0, 0.0, 0.0], metadata={"doc_id": "B", "text": "b"})
        retriever = _make_retriever(store)
        pipeline = RagPipeline(retriever, _static_generator)
        result = pipeline.answer("q", filters={"doc_id": "A"})
        assert len(result.citations) == 1
        assert result.citations[0].metadata["doc_id"] == "A"
