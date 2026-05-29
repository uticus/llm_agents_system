"""HallucinationDetector protocol, HallucinationReport, and built-in detectors.

Two built-in detectors are provided:

* :class:`OverlapDetector` — word-overlap heuristic (token F1 / recall).
  A sentence is considered "supported" when its recall against any reference
  exceeds a threshold.  No model dependencies; runs in pure Python.

* :class:`LLMJudgeDetector` — delegates scoring to a caller-supplied LLM
  callable ``(answer: str, references: list[str]) -> float``.  Useful for
  integrating an LLM-as-judge model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing import Protocol  # type: ignore[assignment]

    from typing_extensions import runtime_checkable


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class HallucinationReport:
    """Result of a hallucination detection run.

    Attributes:
        answer:             The answer that was evaluated.
        groundedness_score: Float in ``[0.0, 1.0]``.
                            ``1.0`` = fully grounded; ``0.0`` = fully hallucinated.
        is_hallucination:   ``True`` when ``groundedness_score`` is below the
                            configured threshold.
        unsupported_spans:  Substrings or sentences flagged as unsupported
                            (empty when fully grounded).
        metadata:           Arbitrary diagnostics from the detector.
    """

    answer: str
    groundedness_score: float
    is_hallucination: bool
    unsupported_spans: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class HallucinationDetector(Protocol):
    """Protocol for hallucination detectors.

    Any object with a matching ``detect`` method satisfies this interface
    without inheriting from :class:`HallucinationDetector`.
    """

    def detect(
        self,
        answer: str,
        references: list[str],
    ) -> HallucinationReport:
        """Score *answer* against *references*.

        Args:
            answer:     The generated text to evaluate.
            references: Ground-truth snippets or retrieved passages used as
                        the evidence base.

        Returns:
            :class:`HallucinationReport` with groundedness score and
            flagged unsupported spans.
        """
        ...


# ---------------------------------------------------------------------------
# OverlapDetector — word-overlap heuristic
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _recall(candidate: str, reference: str) -> float:
    """Token recall of *candidate* against *reference*."""
    cand_tokens = set(_tokenise(candidate))
    ref_tokens = set(_tokenise(reference))
    if not ref_tokens:
        return 1.0 if not cand_tokens else 0.0
    overlap = cand_tokens & ref_tokens
    return len(overlap) / len(cand_tokens) if cand_tokens else 1.0


def _sentence_recall(sentence: str, references: list[str]) -> float:
    """Maximum recall of *sentence* across all *references*."""
    if not references:
        return 0.0
    return max(_recall(sentence, ref) for ref in references)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


class OverlapDetector:
    """Hallucination detector based on word-overlap recall.

    Each sentence in *answer* is scored by its maximum token recall against
    any reference.  Sentences below the *sentence_threshold* are flagged as
    unsupported.  The overall groundedness score is the mean sentence score.

    Args:
        threshold:          Groundedness score below which the answer is
                            marked as a hallucination (default 0.5).
        sentence_threshold: Recall below which a sentence is flagged as
                            unsupported (default 0.3).
    """

    def __init__(
        self,
        threshold: float = 0.5,
        sentence_threshold: float = 0.3,
    ) -> None:
        self.threshold = threshold
        self.sentence_threshold = sentence_threshold

    def detect(
        self,
        answer: str,
        references: list[str],
    ) -> HallucinationReport:
        """Score *answer* using word-overlap recall.

        Args:
            answer:     Generated text.
            references: Ground-truth or context passages.

        Returns:
            :class:`HallucinationReport` with per-sentence analysis.
        """
        sentences = _split_sentences(answer)
        if not sentences:
            return HallucinationReport(
                answer=answer,
                groundedness_score=0.0,
                is_hallucination=True,
                unsupported_spans=[],
                metadata={"method": "overlap"},
            )

        scores: list[float] = []
        unsupported: list[str] = []
        for sent in sentences:
            score = _sentence_recall(sent, references)
            scores.append(score)
            if score < self.sentence_threshold:
                unsupported.append(sent)

        groundedness = sum(scores) / len(scores)
        return HallucinationReport(
            answer=answer,
            groundedness_score=groundedness,
            is_hallucination=groundedness < self.threshold,
            unsupported_spans=unsupported,
            metadata={"method": "overlap", "sentence_scores": scores},
        )


# ---------------------------------------------------------------------------
# LLMJudgeDetector — delegates to a caller-supplied scorer
# ---------------------------------------------------------------------------


class LLMJudgeDetector:
    """Hallucination detector that delegates scoring to a callable.

    Args:
        scorer:    Callable ``(answer: str, references: list[str]) -> float``
                   returning a groundedness score in ``[0.0, 1.0]``.
        threshold: Score below which the answer is marked as a hallucination
                   (default 0.5).
    """

    def __init__(
        self,
        scorer: Any,
        threshold: float = 0.5,
    ) -> None:
        self._scorer = scorer
        self.threshold = threshold

    def detect(
        self,
        answer: str,
        references: list[str],
    ) -> HallucinationReport:
        """Score *answer* via the scorer callable.

        Args:
            answer:     Generated text.
            references: Ground-truth or context passages.

        Returns:
            :class:`HallucinationReport` with the scorer's output.
        """
        score = float(self._scorer(answer, references))
        score = max(0.0, min(1.0, score))  # clamp
        return HallucinationReport(
            answer=answer,
            groundedness_score=score,
            is_hallucination=score < self.threshold,
            unsupported_spans=[],
            metadata={"method": "llm_judge"},
        )
