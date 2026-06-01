# model_hub

Module path: `src/llm_agents/infra/model_hub/`

## Overview

The model hub module provides a uniform interface for loading and managing model backends across a variety of providers: the OpenAI API, HuggingFace transformers, local GGUF quantized models via llama.cpp, and vLLM-served local models. It defines a structural `ModelBackend` Protocol that any adapter must satisfy, a `ModelHub` registry that maps string names to registered backend instances, and four concrete adapter classes: `OpenAIBackend`, `HuggingFaceBackend`, `LlamaCppBackend`, and `VLLMBackend`. The module is designed for a hybrid inference scenario where some requests go to a cloud API (low operational overhead, higher cost) and others go to locally hosted models (higher operational complexity, zero per-token cost). By hiding backend details behind a single `generate(prompt, max_tokens, temperature) -> str` interface, orchestrators and agents can switch between providers through configuration alone, without changing application code.

---

## Public API

Import everything from `llm_agents.infra.model_hub`.

### Exported symbols

| Symbol | Kind | Description |
|---|---|---|
| `ModelBackend` | Protocol | Structural interface that every backend must satisfy. |
| `FakeBackend` | class | Deterministic test stub that cycles through preset responses. |
| `ModelHub` | class | Registry mapping backend names to `ModelBackend` instances. |
| `OpenAIBackend` | class | Async adapter for the OpenAI Chat Completions API. |
| `HuggingFaceBackend` | class | Local inference via `transformers.pipeline`; requires `training` extra. |
| `LlamaCppBackend` | class | GGUF model inference via `llama-cpp-python`; requires `local-inference` extra. |
| `VLLMBackend` | class | High-throughput local inference via `vllm`; requires `local-inference` extra (Linux/CUDA). |

### `ModelBackend` (Protocol)

```python
@runtime_checkable
class ModelBackend(Protocol):
    name: str

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str: ...

    def metadata(self) -> dict[str, Any]: ...
```

Any class with matching `name`, `generate`, and `metadata` members satisfies this interface without inheriting from it. `runtime_checkable` allows `isinstance(obj, ModelBackend)` checks.

### `FakeBackend`

```python
class FakeBackend
    def __init__(self, name: str, responses: list[str]) -> None
```

| Attribute/Method | Description |
|---|---|
| `name` | Backend name string. |
| `call_count` | Number of times `generate` was called. |
| `generate(prompt, max_tokens, temperature)` | Returns the next string in `responses`, cycling when the list is exhausted. |
| `metadata()` | Returns `{"name": ..., "backend": "fake", "max_tokens": 256}`. |

Requires at least one response string; raises `ValueError` if `responses` is empty.

### `ModelHub`

```python
class ModelHub
    def __init__(self, backends: dict[str, Any] | None = None) -> None
```

| Method | Signature | Description |
|---|---|---|
| `register` | `(backend: ModelBackend) -> None` | Register `backend` under its `name`. Overwrites any existing backend with the same name. |
| `get` | `(name: str) -> ModelBackend \| None` | Return the backend for `name`, or `None` if not registered. |
| `list_names` | `() -> list[str]` | Return all registered names in alphabetical order. |
| `__len__` | `() -> int` | Return the number of registered backends. |

### `OpenAIBackend`

```python
class OpenAIBackend
    def __init__(
        self,
        name: str,
        model_id: str = "gpt-4o",
        api_key: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None
```

| Method | Signature | Description |
|---|---|---|
| `generate` | `async (prompt: str, max_tokens: int \| None = None, temperature: float \| None = None) -> str` | Call OpenAI Chat Completions and return the text content. Raises `ImportError` if `openai` is not installed. |
| `metadata` | `() -> dict[str, Any]` | Returns `{"name": ..., "backend": "openai", "model_id": ...}`. |

The `openai` package import is deferred to `generate()` so that importing this class without `openai` installed does not raise at import time. The `api_key` defaults to the `OPENAI_API_KEY` environment variable when `None`.

### `HuggingFaceBackend`

```python
class HuggingFaceBackend
    def __init__(
        self,
        name: str,
        model_id: str,
        *,
        device: str = "cpu",
        torch_dtype: Any = None,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None
```

Wraps `transformers.pipeline("text-generation", ...)`. The pipeline is loaded lazily on the first `generate()` call or `_get_pipeline()` access. `import transformers` is deferred so the class is importable without the `training` extra. Inference runs in `asyncio.get_event_loop().run_in_executor` to avoid blocking the event loop. `temperature=0.0` (default) disables sampling (`do_sample=False`); `temperature>0` enables it. Only the newly generated tokens are returned (`return_full_text=False`).

### `LlamaCppBackend`

```python
class LlamaCppBackend
    def __init__(
        self,
        name: str,
        model_path: str,
        *,
        n_ctx: int = 2048,
        n_gpu_layers: int = 0,
        verbose: bool = False,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None
```

Wraps `llama_cpp.Llama`. `model_path` is the local GGUF file. The model is loaded lazily on the first call. `import llama_cpp` is deferred. Inference runs in a thread-pool executor.

### `VLLMBackend`

```python
class VLLMBackend
    def __init__(
        self,
        name: str,
        model_id: str,
        *,
        gpu_memory_utilization: float = 0.9,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> None
```

Wraps `vllm.LLM` + `vllm.SamplingParams`. The engine is loaded lazily. `import vllm` is deferred in both `_get_llm()` and `generate()`. Inference runs in a thread-pool executor (vLLM's `generate` is synchronous). Requires Linux with a CUDA GPU.

---

## Architecture

### Conceptual view

```
Application / Agent
    |
    | hub.get("gpt-4o")
    v
ModelHub (dict: name -> ModelBackend)
    |
    +-- "gpt-4o"          -> OpenAIBackend      (openai extra, cloud API)
    +-- "mistral-hf"      -> HuggingFaceBackend  (training extra, local GPU/CPU)
    +-- "llama-gguf"      -> LlamaCppBackend     (local-inference extra, GGUF file)
    +-- "llama-vllm"      -> VLLMBackend         (local-inference extra, Linux/CUDA)
    +-- "test-model"      -> FakeBackend         (built-in, deterministic)

Each backend implements:
    .name: str
    async .generate(prompt, max_tokens, temperature) -> str
    .metadata() -> dict
```

### Data flow

1. At startup, the application instantiates a `ModelHub` and calls `hub.register(backend)` for each backend it wants to make available.
2. When an agent or orchestrator needs to generate text, it calls `hub.get("backend-name")` to retrieve the backend instance.
3. It calls `await backend.generate(prompt, max_tokens=256, temperature=0.0)` and receives the generated string.
4. For **OpenAI**: `generate` creates an `AsyncOpenAI` client, calls `client.chat.completions.create(...)`, and extracts `choices[0].message.content`.
5. For **HuggingFace**: `generate` retrieves the lazily-loaded pipeline and dispatches `pipe(prompt, ...)` to the thread-pool executor.
6. For **LlamaCpp**: `generate` retrieves the lazily-loaded `Llama` model and dispatches `model(prompt, ...)` to the thread-pool executor; extracts `choices[0]["text"]`.
7. For **vLLM**: `generate` builds `SamplingParams`, dispatches `llm.generate([prompt], sampling_params)` to the thread-pool executor, and extracts `outputs[0].outputs[0].text`.
8. For **FakeBackend**: `generate` returns the next preset response string (cycling), incrementing `call_count`.

### Key abstractions

**`ModelBackend` Protocol:** Structural typing (duck typing enforced at type-check time) removes the need for every adapter to import from this module. A HuggingFace adapter, a vLLM adapter, or a llama.cpp adapter can each be written independently and registered without a common base class. `runtime_checkable` enables `isinstance` guards where needed (e.g., in the hub's `register` method type checking or in tests).

**`ModelHub` registry:** A simple `dict[str, ModelBackend]` wrapped in a class. The class exists to provide a named API (`register`, `get`, `list_names`, `__len__`) rather than raw dict access, which makes the registry's intent clear and allows future extensions (e.g., lazy loading, health checks) without changing the interface.

**`OpenAIBackend` deferred import:** Deferring `import openai` to `generate()` means that importing `llm_agents.infra.model_hub` in a test environment that lacks the `openai` package does not fail at module load time. The `ImportError` only surfaces when `generate()` is actually called, and the error message directs the user to install the correct optional extra.

**`HuggingFaceBackend` lazy pipeline + `run_in_executor`:** The `transformers.pipeline` is loaded on first `generate()` call and cached. Inference is dispatched to a thread-pool executor so it does not block the event loop, matching the `async` protocol. `do_sample` is set based on `temperature` to avoid transformer warnings about using `temperature=0` with sampling enabled.

**`LlamaCppBackend` lazy model load:** `llama_cpp.Llama` loads the GGUF file from disk on the first call and caches it. Like HuggingFace, inference runs in the thread-pool executor. `n_gpu_layers=0` (default) runs entirely on CPU; setting it enables partial or full GPU offload.

**`VLLMBackend` engine lifetime:** The vLLM `LLM` engine allocates GPU memory at construction time; once loaded, it is reused across all calls. `SamplingParams` is constructed fresh per call (cheap). vLLM's `generate` is synchronous and must be wrapped in `run_in_executor`.

**`FakeBackend` cycling responses:** The cycling behavior (index wraps around with modulo) means that `FakeBackend` with a single response can be used indefinitely without configuring a long list. For single-shot tests, a one-element list suffices; for multi-call tests, the sequence is played back exactly before cycling.

---

## Design decisions and tradeoffs

- **Decision:** `ModelBackend` is a Protocol, not an abstract base class. **Why:** Adapters for HuggingFace, llama.cpp, and vLLM live in optional extras and cannot be required to import from the core `model_hub` module without creating circular or conditional dependencies. Structural typing removes this coupling. **Tradeoff:** Protocol conformance is only checked by static type checkers (mypy/pyright) and `isinstance` at runtime; a class that omits a required method will fail at call time, not at registration time.

- **Decision:** `generate` takes a single `prompt: str` rather than `messages: list[dict]`. **Why:** The hub targets a lower-level interface than the routing layer. Some local backends (llama.cpp, vLLM serving raw completions) do not natively support the chat message format. **Tradeoff:** Chat-format features (system prompts, multi-turn history) must be serialized to a string by the caller before calling `generate`. The `inference_routing` layer sits above the hub and handles chat-format natively via `LLMRequest.messages`.

- **Decision:** `ModelHub` overwrites on re-registration. **Why:** Simplifies live model replacement (e.g., swapping a model checkpoint during development) without a separate `unregister` API. **Tradeoff:** Silent overwrites can mask bugs where the same name is registered twice with different backends due to a configuration error. There is no warning or error on overwrite.

- **Decision:** `OpenAIBackend` creates a new `AsyncOpenAI` client on every `generate()` call. **Why:** Avoids holding a client object in memory for the entire process lifetime, and avoids connection pool management at this level. **Tradeoff:** Per-call client instantiation adds overhead. In high-throughput scenarios, the client should be created once and reused. A future improvement would be to cache the client as an instance attribute.

- **Decision:** `HuggingFaceBackend`, `LlamaCppBackend`, and `VLLMBackend` all use deferred imports and lazy model loading. **Why:** Their dependencies (PyTorch, llama-cpp-python, vllm) are large and environment-specific. Deferring the import to first use means the class is instantiable without the extra installed, and the error is raised at call time with a clear install hint. **Tradeoff:** A misconfigured environment (extra not installed) is only detected at runtime, not at import time; callers who want an early check should call `backend.metadata()` or `backend._get_pipeline()` immediately after construction.

---

## Scaling concerns

- **Per-call client instantiation in `OpenAIBackend`:** Creating a new `AsyncOpenAI` client per call means each call creates and tears down an aiohttp session and connection pool. Under high call rates (>100 calls/second), this is a significant source of latency and socket overhead. The client should be instantiated once and stored as an instance attribute.

- **No health checking:** `ModelHub.get` returns a backend instance without checking whether the backend is reachable or healthy. A hub serving 20 registered backends has no mechanism to exclude a failed backend from dispatch; callers must handle `generate()` failures themselves.

- **No connection pooling for local backends:** Local inference backends (llama.cpp, vLLM) typically have a fixed concurrency limit (e.g., `n_threads` in llama.cpp). The hub does not track in-flight requests per backend, so concurrent calls can exceed the backend's capacity and cause queuing or errors at the backend level.

- **`list_names` sort on every call:** `list_names()` calls `sorted(self._backends)` every time. With a large number of registered backends, this is a O(n log n) operation on every call. The sorted list could be maintained incrementally.

- **No versioning:** Backend registration has no version field. If multiple checkpoint versions of the same model need to coexist (e.g., for A/B testing), they must be registered under distinct names.

---

## Future improvements

- **Cached `AsyncOpenAI` client:** Store the `AsyncOpenAI` client as an instance attribute in `OpenAIBackend`, created once on first `generate()` call and reused thereafter, to avoid per-call overhead.

- **Health-check API:** Add a `health_check(name: str) -> bool` method to `ModelHub` that calls a lightweight probe on the backend (e.g., a token count or a minimal generation) and marks backends as available or unavailable.

- **Concurrency guard per backend:** Add a `max_concurrent: int` metadata field to `ModelBackend` and implement an `asyncio.Semaphore` in `ModelHub.get` or a wrapping dispatcher class that limits in-flight calls per backend.

- **Cached `AsyncOpenAI` client in `OpenAIBackend`:** Store the `AsyncOpenAI` client as an instance attribute, created once on first `generate()` call and reused thereafter, to avoid per-call session setup overhead.

- **MLflow version tracking:** Add a `version: str | None` field to `ModelHub` backend entries and a `register_versioned(backend, version)` method, backed by an MLflow run ID, so that model checkpoints can be tracked and rolled back.

---

## Usage examples

### Registering and using backends

```python
from llm_agents.infra.model_hub import ModelHub, OpenAIBackend, FakeBackend

hub = ModelHub()

# Register a real OpenAI backend
hub.register(OpenAIBackend(name="gpt-4o", model_id="gpt-4o", api_key="sk-..."))

# Register a fake backend for testing another model slot
hub.register(FakeBackend(name="local-mistral", responses=["Mistral says hello."]))

print(hub.list_names())  # ['gpt-4o', 'local-mistral']
print(len(hub))          # 2
```

### Generating text via the hub

```python
from llm_agents.infra.model_hub import ModelHub, FakeBackend

hub = ModelHub()
hub.register(FakeBackend("my-model", responses=["The answer is 42.", "I don't know."]))

backend = hub.get("my-model")
if backend is None:
    raise RuntimeError("backend not found")

result = await backend.generate("What is the answer to life?", max_tokens=128)
print(result)  # "The answer is 42."

meta = backend.metadata()
print(meta)  # {'name': 'my-model', 'backend': 'fake', 'max_tokens': 256}
```

### OpenAI backend with default API key from environment

```python
import os
from llm_agents.infra.model_hub import ModelHub, OpenAIBackend

# OPENAI_API_KEY must be set in the environment
hub = ModelHub()
hub.register(OpenAIBackend(
    name="gpt-4o-mini",
    model_id="gpt-4o-mini",
    max_tokens=512,
    temperature=0.2,
))

backend = hub.get("gpt-4o-mini")
response = await backend.generate("Summarize this document in one sentence.")
print(response)
```

### HuggingFace local inference

```python
# Requires: pip install 'llm-agents-system[training]'
from llm_agents.infra.model_hub import ModelHub, HuggingFaceBackend

hub = ModelHub()
hub.register(HuggingFaceBackend(
    name="gpt2-local",
    model_id="gpt2",
    device="cpu",
    max_tokens=128,
    temperature=0.7,
))

backend = hub.get("gpt2-local")
# Pipeline is loaded lazily on the first generate() call:
result = await backend.generate("Once upon a time")
print(result)
```

### GGUF model via llama.cpp

```python
# Requires: pip install 'llm-agents-system[local-inference]'
from llm_agents.infra.model_hub import ModelHub, LlamaCppBackend

hub = ModelHub()
hub.register(LlamaCppBackend(
    name="llama-7b",
    model_path="/models/llama-2-7b.Q4_K_M.gguf",
    n_ctx=4096,
    n_gpu_layers=0,   # set >0 to offload layers to GPU
    max_tokens=256,
))

result = await hub.get("llama-7b").generate("The capital of France is")
print(result)
```

### vLLM high-throughput backend (Linux/CUDA)

```python
# Requires: pip install 'llm-agents-system[local-inference]'  (Linux only)
from llm_agents.infra.model_hub import ModelHub, VLLMBackend

hub = ModelHub()
hub.register(VLLMBackend(
    name="mistral-vllm",
    model_id="mistralai/Mistral-7B-Instruct-v0.2",
    gpu_memory_utilization=0.85,
    max_tokens=512,
    temperature=0.0,
))

result = await hub.get("mistral-vllm").generate("Explain quantum entanglement briefly.")
print(result)
```
