"""Model hub: load and version models across providers and local backends.

Supports HuggingFace, the OpenAI API, and GGUF quantized models via llama.cpp and vLLM,
behind a uniform ``ModelBackend`` interface; model versions tracked via MLflow.

Local backends require the ``local-inference`` extra; HF/MLflow require ``training``.
"""
