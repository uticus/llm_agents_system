"""Unit tests for serving/api: health, chat, rag/answer endpoints."""

from __future__ import annotations

import asyncio

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from llm_agents.serving.api import create_app  # noqa: E402
from llm_agents.serving.api._schemas import ChatResponse, HealthResponse, RagResponse  # noqa: E402


# ---------------------------------------------------------------------------
# Mock sub-systems
# ---------------------------------------------------------------------------


class _FakeRouter:
    """Minimal inference router that returns a canned response."""

    async def complete(self, request):
        from llm_agents.infra.inference_routing._models import LLMResponse

        return LLMResponse(
            model=request.model,
            content="Hello from mock",
            prompt_tokens=5,
            completion_tokens=3,
            latency_s=0.01,
        )


class _FakeRagPipeline:
    """Minimal RAG pipeline returning a static grounded answer."""

    def answer(self, query: str, **kwargs):
        from llm_agents.rag.pipeline._pipeline import GroundedAnswer
        from llm_agents.rag.retrieval._retriever import RetrievedPassage

        return GroundedAnswer(
            query=query,
            answer=f"Answer to: {query}",
            citations=[
                RetrievedPassage(doc_id="c1", text="context text", score=0.9)
            ],
        )


class _BlockingGuardrail:
    """Guardrail that always blocks."""

    def run(self, text: str):
        from llm_agents.infra.guardrails._models import GuardResult

        return GuardResult.block(text, "forbidden content")


class _PassthroughGuardrail:
    """Guardrail that always passes."""

    def run(self, text: str):
        from llm_agents.infra.guardrails._models import GuardResult

        return GuardResult.pass_(text)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_no_services():
    """App with no sub-systems configured."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def client_full():
    """App with mock router and RAG pipeline."""
    app = create_app(
        router=_FakeRouter(),
        rag_pipeline=_FakeRagPipeline(),
    )
    return TestClient(app)


@pytest.fixture
def client_with_blocking_guardrail():
    """App with blocking guardrail."""
    app = create_app(
        router=_FakeRouter(),
        rag_pipeline=_FakeRagPipeline(),
        guardrail_chain=_BlockingGuardrail(),
    )
    return TestClient(app)


@pytest.fixture
def client_with_passthrough_guardrail():
    """App with passthrough guardrail."""
    app = create_app(
        router=_FakeRouter(),
        rag_pipeline=_FakeRagPipeline(),
        guardrail_chain=_PassthroughGuardrail(),
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_get_health_200(self, client_no_services) -> None:
        resp = client_no_services.get("/health")
        assert resp.status_code == 200

    def test_health_body(self, client_no_services) -> None:
        resp = client_no_services.get("/health")
        body = resp.json()
        assert body["status"] == "ok"

    def test_health_version_present(self, client_no_services) -> None:
        resp = client_no_services.get("/health")
        assert "version" in resp.json()


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    def test_chat_200(self, client_full) -> None:
        resp = client_full.post("/chat", json={"prompt": "Hello"})
        assert resp.status_code == 200

    def test_chat_response_fields(self, client_full) -> None:
        resp = client_full.post("/chat", json={"prompt": "Hello"})
        body = resp.json()
        assert "answer" in body
        assert "model" in body
        assert body["answer"] == "Hello from mock"

    def test_chat_model_field_forwarded(self, client_full) -> None:
        resp = client_full.post(
            "/chat", json={"prompt": "Hi", "model": "gpt-4o"}
        )
        assert resp.json()["model"] == "gpt-4o"

    def test_chat_no_router_503(self, client_no_services) -> None:
        resp = client_no_services.post("/chat", json={"prompt": "Hello"})
        assert resp.status_code == 503

    def test_chat_empty_prompt_422(self, client_full) -> None:
        resp = client_full.post("/chat", json={"prompt": ""})
        assert resp.status_code == 422

    def test_chat_missing_prompt_422(self, client_full) -> None:
        resp = client_full.post("/chat", json={})
        assert resp.status_code == 422

    def test_chat_blocked_by_guardrail_400(self, client_with_blocking_guardrail) -> None:
        resp = client_with_blocking_guardrail.post("/chat", json={"prompt": "bad content"})
        assert resp.status_code == 400

    def test_chat_passes_guardrail(self, client_with_passthrough_guardrail) -> None:
        resp = client_with_passthrough_guardrail.post("/chat", json={"prompt": "hello"})
        assert resp.status_code == 200

    def test_chat_token_counts(self, client_full) -> None:
        resp = client_full.post("/chat", json={"prompt": "Hello"})
        body = resp.json()
        assert body["prompt_tokens"] == 5
        assert body["completion_tokens"] == 3


# ---------------------------------------------------------------------------
# /rag/answer
# ---------------------------------------------------------------------------


class TestRagAnswerEndpoint:
    def test_rag_200(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": "What is X?"})
        assert resp.status_code == 200

    def test_rag_response_fields(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": "What is X?"})
        body = resp.json()
        assert "answer" in body
        assert "citations" in body

    def test_rag_answer_content(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": "test?"})
        assert "test?" in resp.json()["answer"]

    def test_rag_citations_structure(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": "q"})
        citations = resp.json()["citations"]
        assert len(citations) == 1
        assert citations[0]["doc_id"] == "c1"
        assert citations[0]["text"] == "context text"
        assert citations[0]["score"] == pytest.approx(0.9)

    def test_rag_no_pipeline_503(self, client_no_services) -> None:
        resp = client_no_services.post("/rag/answer", json={"query": "q"})
        assert resp.status_code == 503

    def test_rag_empty_query_422(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": ""})
        assert resp.status_code == 422

    def test_rag_blocked_by_guardrail_400(self, client_with_blocking_guardrail) -> None:
        resp = client_with_blocking_guardrail.post(
            "/rag/answer", json={"query": "bad query"}
        )
        assert resp.status_code == 400

    def test_rag_top_k_forwarded(self, client_full) -> None:
        resp = client_full.post("/rag/answer", json={"query": "q", "top_k": 3})
        assert resp.status_code == 200

    def test_rag_filters_forwarded(self, client_full) -> None:
        resp = client_full.post(
            "/rag/answer", json={"query": "q", "filters": {"doc_id": "A"}}
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_chat_response_defaults(self) -> None:
        cr = ChatResponse(answer="x", model="m")
        assert cr.prompt_tokens == 0
        assert cr.completion_tokens == 0

    def test_health_response_defaults(self) -> None:
        hr = HealthResponse()
        assert hr.status == "ok"

    def test_rag_response_no_citations(self) -> None:
        rr = RagResponse(answer="x", citations=[])
        assert rr.citations == []
