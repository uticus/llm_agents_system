"""Unit tests for rag/reranking: Reranker, FakeReranker, ScoreReranker."""

from __future__ import annotations

from llm_agents.rag.reranking import FakeReranker, Reranker, ScoreReranker
from llm_agents.rag.retrieval import RetrievedPassage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _passages(*texts: str) -> list[RetrievedPassage]:
    return [RetrievedPassage(doc_id=str(i), text=t, score=0.5) for i, t in enumerate(texts)]


# ---------------------------------------------------------------------------
# Reranker protocol
# ---------------------------------------------------------------------------


class TestRerankerProtocol:
    def test_fake_reranker_satisfies_protocol(self) -> None:
        fr = FakeReranker()
        assert isinstance(fr, Reranker)

    def test_score_reranker_satisfies_protocol(self) -> None:
        def scorer(query, passage):
            return 1.0

        sr = ScoreReranker(scorer)
        assert isinstance(sr, Reranker)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyReranker:
            def rerank(self, query, passages, *, top_n=None):
                return passages

        assert isinstance(MyReranker(), Reranker)

    def test_missing_rerank_fails_protocol(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), Reranker)


# ---------------------------------------------------------------------------
# FakeReranker
# ---------------------------------------------------------------------------


class TestFakeReranker:
    def test_reverses_order(self) -> None:
        fr = FakeReranker()
        ps = _passages("a", "b", "c")
        result = fr.rerank("q", ps)
        assert [r.text for r in result] == ["c", "b", "a"]

    def test_empty_list(self) -> None:
        fr = FakeReranker()
        assert fr.rerank("q", []) == []

    def test_top_n_truncates(self) -> None:
        fr = FakeReranker(top_n=2)
        ps = _passages("a", "b", "c", "d")
        result = fr.rerank("q", ps)
        assert len(result) == 2

    def test_per_call_top_n_override(self) -> None:
        fr = FakeReranker(top_n=10)
        ps = _passages("a", "b", "c")
        result = fr.rerank("q", ps, top_n=1)
        assert len(result) == 1

    def test_none_top_n_keeps_all(self) -> None:
        fr = FakeReranker()
        ps = _passages("a", "b", "c", "d")
        result = fr.rerank("q", ps)
        assert len(result) == 4

    def test_rerank_count_incremented(self) -> None:
        fr = FakeReranker()
        assert fr.rerank_count == 0
        fr.rerank("q", _passages("a"))
        fr.rerank("q", _passages("b"))
        assert fr.rerank_count == 2

    def test_single_passage(self) -> None:
        fr = FakeReranker()
        ps = _passages("only")
        result = fr.rerank("q", ps)
        assert len(result) == 1
        assert result[0].text == "only"

    def test_does_not_mutate_input(self) -> None:
        fr = FakeReranker()
        ps = _passages("a", "b", "c")
        original_ids = [p.doc_id for p in ps]
        fr.rerank("q", ps)
        assert [p.doc_id for p in ps] == original_ids


# ---------------------------------------------------------------------------
# ScoreReranker
# ---------------------------------------------------------------------------


class TestScoreReranker:
    def test_sorts_by_scorer_descending(self) -> None:
        scores_map = {"0": 0.1, "1": 0.9, "2": 0.5}

        def scorer(query, passage):
            return scores_map[passage.doc_id]

        sr = ScoreReranker(scorer)
        ps = _passages("low", "high", "mid")
        result = sr.rerank("q", ps)
        assert [r.doc_id for r in result] == ["1", "2", "0"]

    def test_top_n_truncates(self) -> None:
        def scorer(query, passage):
            return float(passage.doc_id)

        sr = ScoreReranker(scorer, top_n=2)
        ps = _passages("0", "1", "2", "3")
        result = sr.rerank("q", ps)
        assert len(result) == 2

    def test_per_call_top_n_override(self) -> None:
        def scorer(query, passage):
            return 1.0

        sr = ScoreReranker(scorer, top_n=100)
        ps = _passages("a", "b", "c")
        result = sr.rerank("q", ps, top_n=1)
        assert len(result) == 1

    def test_empty_list(self) -> None:
        sr = ScoreReranker(lambda q, p: 1.0)
        assert sr.rerank("q", []) == []

    def test_rerank_count_incremented(self) -> None:
        sr = ScoreReranker(lambda q, p: 1.0)
        sr.rerank("q", _passages("a"))
        sr.rerank("q", _passages("b"))
        assert sr.rerank_count == 2

    def test_query_passed_to_scorer(self) -> None:
        received: list[str] = []

        def scorer(query, passage):
            received.append(query)
            return 1.0

        sr = ScoreReranker(scorer)
        sr.rerank("my query", _passages("a", "b"))
        assert all(q == "my query" for q in received)
