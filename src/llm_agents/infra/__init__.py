"""Runtime infrastructure (cross-cutting concerns).

Subsystems:
    model_hub                  load/version models across HF, OpenAI, GGUF, vLLM
    inference_routing          route requests across providers/models by policy
    cost_latency_optimization  caching, batching, and model-tier selection
    guardrails                 output filtering and tone/compliance enforcement
    tracing                    structured spans across agent/tool/LLM calls
    observability              metrics, logging, and dashboards
"""

__all__ = [
    "model_hub",
    "inference_routing",
    "cost_latency_optimization",
    "guardrails",
    "tracing",
    "observability",
]
