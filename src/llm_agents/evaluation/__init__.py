"""Offline evaluation and benchmarking.

Subsystems:
    framework      metrics (incl. BLEU/ROUGE/F1), harnesses, and scoring
    prompts        test, score, and compare prompt variants; consistency tests
    benchmarking   run agents against task suites and aggregate results
    hallucination  detect hallucinations by comparison with ground-truth snippets
"""

__all__ = [
    "framework",
    "prompts",
    "benchmarking",
    "hallucination",
]
