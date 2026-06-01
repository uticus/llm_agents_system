"""Model hub: load and version models across providers and local backends.

Supports HuggingFace, the OpenAI API, and GGUF quantized models via llama.cpp and vLLM,
behind a uniform ``ModelBackend`` interface; model versions tracked via MLflow.

Local backends require the ``local-inference`` extra; HF requires ``training``;
OpenAI requires ``openai``.

Public surface
--------------
Protocol and fake backend::

    from llm_agents.infra.model_hub import ModelBackend, FakeBackend

Registry::

    from llm_agents.infra.model_hub import ModelHub

Provider adapters (deferred imports — no extra needed to import the class)::

    from llm_agents.infra.model_hub import OpenAIBackend
    from llm_agents.infra.model_hub import HuggingFaceBackend
    from llm_agents.infra.model_hub import LlamaCppBackend
    from llm_agents.infra.model_hub import VLLMBackend
"""

from llm_agents.infra.model_hub._backend import FakeBackend, ModelBackend
from llm_agents.infra.model_hub._hub import ModelHub
from llm_agents.infra.model_hub._huggingface_backend import HuggingFaceBackend
from llm_agents.infra.model_hub._llamacpp_backend import LlamaCppBackend
from llm_agents.infra.model_hub._openai_backend import OpenAIBackend
from llm_agents.infra.model_hub._vllm_backend import VLLMBackend

__all__ = [
    "FakeBackend",
    "HuggingFaceBackend",
    "LlamaCppBackend",
    "ModelBackend",
    "ModelHub",
    "OpenAIBackend",
    "VLLMBackend",
]
