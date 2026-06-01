"""Unit tests for evaluation/hallucination.

Covers: HallucinationReport, OverlapDetector, LLMJudgeDetector.
"""

from __future__ import annotations

import pytest

from llm_agents.evaluation.hallucination import (
    HallucinationDetector,
    HallucinationReport,
    LLMJudgeDetector,
    OverlapDetector,
)

# ---------------------------------------------------------------------------
# HallucinationReport
# ---------------------------------------------------------------------------


class TestHallucinationReport:
    def test_required_fields(self) -> None:
        r = HallucinationReport(
            answer="some answer",
            groundedness_score=0.8,
            is_hallucination=False,
        )
        assert r.answer == "some answer"
        assert r.groundedness_score == 0.8
        assert r.is_hallucination is False

    def test_defaults(self) -> None:
        r = HallucinationReport(answer="x", groundedness_score=0.5, is_hallucination=False)
        assert r.unsupported_spans == []
        assert r.metadata == {}

    def test_with_unsupported_spans(self) -> None:
        r = HallucinationReport(
            answer="x",
            groundedness_score=0.1,
            is_hallucination=True,
            unsupported_spans=["claim1", "claim2"],
        )
        assert len(r.unsupported_spans) == 2


# ---------------------------------------------------------------------------
# HallucinationDetector protocol
# ---------------------------------------------------------------------------


class TestHallucinationDetectorProtocol:
    def test_overlap_detector_satisfies_protocol(self) -> None:
        assert isinstance(OverlapDetector(), HallucinationDetector)

    def test_llm_judge_satisfies_protocol(self) -> None:
        assert isinstance(LLMJudgeDetector(scorer=lambda a, r: 0.9), HallucinationDetector)

    def test_plain_class_satisfies_protocol(self) -> None:
        class MyDetector:
            def detect(self, answer, references):
                return HallucinationReport(
                    answer=answer,
                    groundedness_score=1.0,
                    is_hallucination=False,
                )

        assert isinstance(MyDetector(), HallucinationDetector)

    def test_missing_detect_fails_protocol(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), HallucinationDetector)


# ---------------------------------------------------------------------------
# OverlapDetector — supported answers
# ---------------------------------------------------------------------------


class TestOverlapDetectorSupported:
    def test_identical_answer_is_grounded(self) -> None:
        detector = OverlapDetector(threshold=0.5)
        references = ["The sky is blue."]
        report = detector.detect("The sky is blue.", references)
        assert report.groundedness_score >= 0.9
        assert report.is_hallucination is False

    def test_high_overlap_is_grounded(self) -> None:
        detector = OverlapDetector(threshold=0.5)
        refs = ["Paris is the capital of France."]
        report = detector.detect("Paris is the capital of France", refs)
        assert report.is_hallucination is False
        assert report.unsupported_spans == []

    def test_returns_report_instance(self) -> None:
        detector = OverlapDetector()
        report = detector.detect("some text", ["some reference"])
        assert isinstance(report, HallucinationReport)

    def test_method_in_metadata(self) -> None:
        detector = OverlapDetector()
        report = detector.detect("x", ["x"])
        assert report.metadata.get("method") == "overlap"


# ---------------------------------------------------------------------------
# OverlapDetector — unsupported answers
# ---------------------------------------------------------------------------


class TestOverlapDetectorUnsupported:
    def test_unrelated_answer_is_hallucination(self) -> None:
        detector = OverlapDetector(threshold=0.5, sentence_threshold=0.3)
        refs = ["The sky is blue."]
        report = detector.detect("Elephants can fly.", refs)
        assert report.is_hallucination is True

    def test_unsupported_spans_populated(self) -> None:
        detector = OverlapDetector(threshold=0.5, sentence_threshold=0.9)
        refs = ["Paris is in France."]
        # "Elephants fly" won't match the reference
        report = detector.detect("Elephants fly.", refs)
        assert len(report.unsupported_spans) > 0

    def test_empty_references_hallucination(self) -> None:
        detector = OverlapDetector(threshold=0.5)
        report = detector.detect("Some answer.", [])
        assert report.is_hallucination is True

    def test_empty_answer(self) -> None:
        detector = OverlapDetector()
        report = detector.detect("", ["reference text"])
        assert report.groundedness_score == 0.0
        assert report.is_hallucination is True


# ---------------------------------------------------------------------------
# OverlapDetector — partial support
# ---------------------------------------------------------------------------


class TestOverlapDetectorPartial:
    def test_partially_supported(self) -> None:
        detector = OverlapDetector(threshold=0.5, sentence_threshold=0.3)
        # First sentence is grounded, second is not
        refs = ["Paris is in France."]
        answer = "Paris is in France. Elephants can fly."
        report = detector.detect(answer, refs)
        # Score should be between 0 and 1 (partial)
        assert 0.0 < report.groundedness_score < 1.0

    def test_threshold_controls_flag(self) -> None:
        refs = ["some reference word"]
        detector_strict = OverlapDetector(threshold=0.9)
        detector_lenient = OverlapDetector(threshold=0.1)
        answer = "some partial match"
        report_strict = detector_strict.detect(answer, refs)
        report_lenient = detector_lenient.detect(answer, refs)
        # Strict threshold should flag more
        assert report_strict.groundedness_score == report_lenient.groundedness_score
        assert report_strict.is_hallucination or not report_lenient.is_hallucination


# ---------------------------------------------------------------------------
# LLMJudgeDetector
# ---------------------------------------------------------------------------


class TestLLMJudgeDetector:
    def test_high_score_not_hallucination(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.9, threshold=0.5)
        report = detector.detect("answer", ["ref"])
        assert report.groundedness_score == pytest.approx(0.9)
        assert report.is_hallucination is False

    def test_low_score_is_hallucination(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.1, threshold=0.5)
        report = detector.detect("answer", ["ref"])
        assert report.is_hallucination is True

    def test_score_clamped_above_one(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 1.5)
        report = detector.detect("x", ["y"])
        assert report.groundedness_score == pytest.approx(1.0)

    def test_score_clamped_below_zero(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: -0.5)
        report = detector.detect("x", ["y"])
        assert report.groundedness_score == pytest.approx(0.0)

    def test_scorer_receives_answer_and_references(self) -> None:
        received: list[tuple] = []

        def scorer(answer, references):
            received.append((answer, references))
            return 1.0

        detector = LLMJudgeDetector(scorer=scorer)
        detector.detect("my answer", ["ref1", "ref2"])
        assert received == [("my answer", ["ref1", "ref2"])]

    def test_method_in_metadata(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.8)
        report = detector.detect("x", ["y"])
        assert report.metadata.get("method") == "llm_judge"

    def test_returns_report_instance(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.7)
        report = detector.detect("answer", ["ref"])
        assert isinstance(report, HallucinationReport)

    def test_threshold_at_boundary(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.5, threshold=0.5)
        report = detector.detect("x", ["y"])
        # score == threshold => NOT a hallucination (score < threshold)
        assert report.is_hallucination is False

    def test_empty_references(self) -> None:
        detector = LLMJudgeDetector(scorer=lambda a, r: 0.8)
        report = detector.detect("answer", [])
        assert isinstance(report, HallucinationReport)
