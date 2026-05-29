# serving/api

## Overview

The `serving/api` module exposes the llm_agents_system platform as a FastAPI HTTP service. It provides three endpoints: a liveness health check, a single-turn chat/completion endpoint, and a retrieval-augmented generation (RAG) answer endpoint. The module is structured as a factory (`create_app`) that assembles a FastAPI application with all subsystems injected via `app.state`, keeping route handlers testable without a live event loop. All request and response shapes are defined as Pydantic models, enabling automatic OpenAPI schema generation. An optional guardrail chain can be injected to screen prompts before they reach the inference router or RAG pipeline. The module is gated behind the `serving` optional extra (FastAPI + Starlette); importing it without that extra installed fails only at `create_app` call time, not at import time.

---

## Public API

### Exported symbols

| Name | Kind | Description |
|---|---|---|
| `create_app` | function | Assemble and return a configured FastAPI application. |
| `ChatRequest` | Pydantic model | Request body for `POST /chat`. |
| `ChatResponse` | Pydantic model | Response body for `POST /chat`. |
| `RagRequest` | Pydantic model | Request body for `POST /rag/answer`. |
| `RagResponse` | Pydantic model | Response body for `POST /rag/answer`. |
| `CitationSchema` | Pydantic model | A single cited passage within a `RagResponse`. |
| `HealthResponse` | Pydantic model | Response body for `GET /health`. |

### create_app

```
create_app(
    *,
    router: Any = None,              # inference router; None -> /chat returns 503
    rag_pipeline: Any = None,        # RAG pipeline; None -> /rag/answer returns 503
    guardrail_chain: Any = None,     # optional guardrail chain applied to all prompts
    title: str = "LLM Agents API",
    version: str = "0.1.0",
) -> fastapi.FastAPI
```

Raises `ImportError` if FastAPI is not installed.

### ChatRequest

```
ChatRequest(
    prompt: str,          # min_length=1
    model: str = "default",
    max_tokens: int = 256,  # ge=1
    temperature: float = 0.0,  # ge=0.0, le=2.0
)
```

### ChatResponse

```
ChatResponse(
    answer: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
)
```

### RagRequest

```
RagRequest(
    query: str,           # min_length=1
    top_k: int = 5,       # ge=1
    filters: dict[str, str] | None = None,
)
```

### CitationSchema

```
CitationSchema(
    doc_id: str,
    text: str,
    score: float,
)
```

### RagResponse

```
RagResponse(
    answer: str,
    citations: list[CitationSchema],
)
```

### HealthResponse

```
HealthResponse(
    status: str = "ok",
    version: str = "0.1.0",
)
```

### ErrorResponse (internal)

```
ErrorResponse(
    error: str,
    detail: str | None = None,
)
```

Used as the structured body for 4xx/5xx responses. Not exported in `__all__` but importable from `llm_agents.serving.api._schemas`.

---

## Architecture

### Conceptual view

```
           HTTP client
               |
         FastAPI app
         (create_app)
         /     |      \
  GET /health  |    POST /rag/answer
         POST /chat
               |
         app.state
         /    |    \
   router  rag_   guardrail_
           pipeline  chain
               |
        inference_routing  RAG pipeline
        (LLMRequest ->     (.answer() ->
         LLMResponse)       GroundedAnswer)
```

### Data flow — POST /chat

1. FastAPI deserialises the JSON body into a `ChatRequest`. Pydantic validation rejects malformed input (400 response from FastAPI automatically).
2. The route handler reads `request.app.state.inference_router`. If `None`, raises `HTTPException(503)`.
3. If `guardrail_chain` is set, `guardrail_chain.run(prompt)` is called. If `result.passed` is `False`, raises `HTTPException(400, detail=result.violation_detail)`. If passed, the potentially sanitised `result.text` replaces the raw prompt.
4. An `LLMRequest` is constructed from the body fields (`model`, `messages`, `max_tokens`, `temperature`).
5. The route handler checks whether `inference_router.complete` is a coroutine function (`asyncio.iscoroutinefunction`) and either `await`s it or calls it synchronously.
6. The `LLMResponse` is mapped to a `ChatResponse` and serialised to JSON.

### Data flow — POST /rag/answer

1. FastAPI deserialises the body into a `RagRequest`.
2. The route handler reads `request.app.state.rag_pipeline`. If `None`, raises `HTTPException(503)`.
3. Guardrail check on `body.query` (same logic as `/chat`).
4. `rag_pipeline.answer(query, top_k=body.top_k, filters=body.filters)` is called (synchronously — no `await`).
5. Each passage in `grounded.citations` is mapped to a `CitationSchema`.
6. A `RagResponse` is returned.

### Data flow — GET /health

Returns `HealthResponse(status="ok", version="0.1.0")` unconditionally with HTTP 200.

### Key abstractions

**`app.state` dependency injection**: FastAPI's `app.state` is a namespace object that the application factory populates at startup. Route handlers access it via `request.app.state`. This design makes the handlers unit-testable: tests can construct a mock `Request` object with a mock `app.state` rather than starting a real server.

**`build_router()` function**: the API router is built by a free function rather than at module level. This defers FastAPI imports to `_app.py`, keeping `_schemas.py` importable without FastAPI installed (schemas only need Pydantic). `build_router` is called once per `create_app` invocation.

**Async/sync inference router compatibility**: the `/chat` handler checks `asyncio.iscoroutinefunction(inference_router.complete)` to support both async and sync router implementations. This adds flexibility for routers backed by blocking HTTP clients or local models that have not been made async.

**Guardrail chain**: the module does not define the guardrail chain protocol itself; it only requires that the chain have a `run(text)` method returning an object with `passed: bool` and `text: str` attributes. This decouples the API layer from the guardrails module.

---

## Design decisions and tradeoffs

- **Decision**: `create_app` uses keyword-only arguments (`*`) for all parameters after `self`. **Why**: Prevents accidental positional-argument mistakes when calling `create_app(my_router, my_rag)` in the wrong order — a subtle bug that would be hard to diagnose. **Tradeoff**: Callers must always use keyword syntax, which is slightly more verbose.

- **Decision**: The router and RAG pipeline are optional and return 503 when absent. **Why**: Allows the application to start and serve `/health` even if only some backends are configured, enabling incremental deployment (e.g., deploy chat endpoint before RAG). **Tradeoff**: Callers receive a 503 rather than a startup-time error, which may be harder to diagnose in a misconfigured deployment.

- **Decision**: FastAPI import is deferred to inside `create_app` rather than at module import time. **Why**: Allows `from llm_agents.serving.api import ChatRequest, ChatResponse` to work without FastAPI installed, which is useful for client libraries or offline schema validation. **Tradeoff**: The `ImportError` for missing FastAPI surfaces at runtime (first `create_app` call) rather than at import time.

- **Decision**: The RAG pipeline's `answer` method is called synchronously (no `await`). **Why**: The current RAG pipeline design is synchronous. Adding `await` would require the pipeline to be async, adding complexity. **Tradeoff**: If the RAG pipeline blocks the event loop (e.g., on a slow vector store query), it will degrade concurrency for all requests being handled by the same FastAPI worker.

- **Decision**: `ErrorResponse` is defined in `_schemas.py` but not exported in `__all__`. **Why**: It is an internal implementation detail used by route handlers for structured error bodies; it is not part of the stable public surface that client code should import. **Tradeoff**: Advanced users who want to reconstruct error bodies programmatically cannot find it via `from llm_agents.serving.api import ErrorResponse` without knowing to import from `_schemas` directly.

---

## Scaling concerns

FastAPI with an ASGI server (Uvicorn, Hypercorn) handles concurrent requests via asyncio. The `/health` endpoint is entirely non-blocking. The `/chat` endpoint's concurrency is limited by the inference router: if the router calls a remote API, each in-flight request holds one asyncio coroutine, which is cheap. If the router is synchronous and CPU-bound, it will block the event loop and degrade all other concurrent requests. The `/rag/answer` endpoint calls the RAG pipeline synchronously, which is a potential event-loop blocker under load.

The application itself has no connection pooling, request queuing, or backpressure mechanisms. These are expected to be provided by the ASGI server (worker count, request queue) and the upstream load balancer.

**What breaks first**: event-loop blocking from the synchronous RAG pipeline under concurrent load.

**Ceiling**: throughput is bounded by the slowest synchronous operation in any request path.

---

## Future improvements

- **Async RAG pipeline**: make the RAG pipeline call awaitable (`await rag_pipeline.answer(...)`) or wrap the synchronous call in `asyncio.to_thread` to avoid blocking the event loop.
- **Request ID middleware**: add a Starlette middleware that generates a UUID request ID per request, attaches it to response headers, and propagates it into log records for distributed tracing.
- **Authentication middleware**: add API-key or JWT bearer token authentication middleware. Currently the API is completely open.
- **Rate limiting**: add per-client request rate limiting (e.g., using `slowapi`) to protect the inference backend from overload.
- **Streaming responses**: add a `POST /chat/stream` endpoint that uses `StreamingResponse` to stream LLM tokens to the client as they are generated, reducing time-to-first-token perceived by users.
- **Structured logging**: add request/response logging middleware that records method, path, status code, and latency in a structured JSON format compatible with log aggregation systems.

---

## Endpoints reference

| Method | Path | Request body | Response body | Error codes |
|---|---|---|---|---|
| GET | `/health` | none | `HealthResponse` | none |
| POST | `/chat` | `ChatRequest` | `ChatResponse` | 400 (guardrail block), 422 (validation), 503 (router not configured) |
| POST | `/rag/answer` | `RagRequest` | `RagResponse` | 400 (guardrail block), 422 (validation), 503 (RAG pipeline not configured) |

### GET /health

Always returns HTTP 200. Used by load balancers and orchestrators for liveness probing.

Request: no body.

Response:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### POST /chat

Sends a user prompt to the configured inference router and returns the model's response.

Request:
```json
{
  "prompt": "What is the capital of France?",
  "model": "default",
  "max_tokens": 256,
  "temperature": 0.0
}
```

- `prompt`: required, non-empty string.
- `model`: model identifier forwarded to the router. Default `"default"`.
- `max_tokens`: integer >= 1. Default `256`.
- `temperature`: float in [0.0, 2.0]. Default `0.0`.

Response (200):
```json
{
  "answer": "Paris",
  "model": "gpt-4",
  "prompt_tokens": 12,
  "completion_tokens": 3
}
```

Error codes:
- `400`: prompt blocked by the guardrail chain. Body: `{"detail": "Prompt blocked by guardrail: <violation_detail>"}`.
- `422`: Pydantic validation failure (missing `prompt`, out-of-range `temperature`, etc.).
- `503`: inference router not configured. Body: `{"detail": "Inference router not configured."}`.

### POST /rag/answer

Retrieves relevant passages and generates a grounded answer.

Request:
```json
{
  "query": "Who invented the telephone?",
  "top_k": 5,
  "filters": {"source": "wikipedia"}
}
```

- `query`: required, non-empty string.
- `top_k`: number of passages to retrieve. Integer >= 1. Default `5`.
- `filters`: optional string-to-string metadata filter map forwarded to the retriever. Default `null`.

Response (200):
```json
{
  "answer": "Alexander Graham Bell is credited with inventing the telephone.",
  "citations": [
    {
      "doc_id": "wiki-telephone-001",
      "text": "Alexander Graham Bell ... was awarded the first US patent for the telephone.",
      "score": 0.93
    }
  ]
}
```

Error codes:
- `400`: query blocked by the guardrail chain. Body: `{"detail": "Query blocked by guardrail: <violation_detail>"}`.
- `422`: Pydantic validation failure.
- `503`: RAG pipeline not configured. Body: `{"detail": "RAG pipeline not configured."}`.

---

## Usage examples

Creating and running the API locally:

```python
from llm_agents.serving.api import create_app

app = create_app(
    router=my_inference_router,
    rag_pipeline=my_rag_pipeline,
)

# Run with uvicorn:
# uvicorn mymodule:app --host 0.0.0.0 --port 8080
```

Chat-only deployment (no RAG):

```python
from llm_agents.serving.api import create_app

app = create_app(router=my_inference_router)
# /rag/answer will return 503; /chat and /health are functional
```

With guardrails:

```python
from llm_agents.serving.api import create_app

app = create_app(
    router=my_router,
    rag_pipeline=my_rag,
    guardrail_chain=my_guardrail_chain,
)
```

Importing schemas without FastAPI (e.g., in a client library):

```python
from llm_agents.serving.api import ChatRequest, ChatResponse, RagRequest

req = ChatRequest(prompt="Hello", model="gpt-4", max_tokens=100)
print(req.model_dump())
```
