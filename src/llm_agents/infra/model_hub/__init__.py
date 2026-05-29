"""Model hub: load and version models across providers and local backends.

Supports HuggingFace, the OpenAI API, and GGUF quantized models via llama.cpp and vLLM,
behind a uniform ``ModelBackend`` interface; model versions tracked via MLflow.

Local backends require the ``local-inference`` extra; HF/MLflow require ``training``.

Public surface
--------------
Protocol and fake backend::

    from llm_agents.infra.model_hub import ModelBackend, FakeBackend

Registry::

    from llm_agents.infra.model_hub import ModelHub

OpenAI adapter (requires ``openai`` package)::

    from llm_agents.infra.model_hub import OpenAIBackend
"""

from llm_agents.infra.model_hub._backend import FakeBackend, ModelBackend
from llm_agents.infra.model_hub._hub import ModelHub
from llm_agents.infra.model_hub._openai_backend import OpenAIBackend

__all__ = [
    "FakeBackend",
    "ModelBackend",
    "ModelHub",
    "OpenAIBackend",
]
