"""Unit tests for the concrete benchmark task suites.

Covers:
- Suite.from_jsonl() — JSONL loading
- arithmetic suite + agent
- qa_lookup suite + agent
- hallucination suite + agent
- classification suite + agent
- BUILTIN_SUITES / BUILTIN_AGENTS registries
- CLI --suite all
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from llm_agents.evaluation.benchmarking import BUILTIN_AGENTS, BUILTIN_SUITES, BenchmarkRunner
from llm_agents.evaluation.benchmarking._models import Suite
from llm_agents.evaluation.benchmarking._suites import (
    _NEGATIVE_WORDS,
    _POSITIVE_WORDS,
    arithmetic_agent,
    arithmetic_suite,
    classification_agent,
    classification_suite,
    hallucination_agent,
    hallucination_suite,
    qa_lookup_agent,
    qa_lookup_suite,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "sample.jsonl"


# ---------------------------------------------------------------------------
# T1: Suite.from_jsonl
# ---------------------------------------------------------------------------


class TestSuiteFromJsonl:
    def test_loads_correct_number_of_tasks(self) -> None:
        suite = Suite.from_jsonl(_FIXTURE)
        # fixture has 3 non-empty lines (one blank line is skipped)
        assert len(suite.tasks) == 3

    def test_task_fields_round_trip(self) -> None:
        suite = Suite.from_jsonl(_FIXTURE)
        t1 = suite.tasks[0]
        assert t1.task_id == "s1"
        assert t1.input == "hello"
        assert t1.expected_output == "hello"

    def test_metadata_present_when_supplied(self) -> None:
        suite = Suite.from_jsonl(_FIXTURE)
        assert suite.tasks[0].metadata == {"category": "echo"}

    def test_metadata_empty_dict_when_absent(self) -> None:
        # task s2 has no "metadata" key in the JSONL line
        suite = Suite.from_jsonl(_FIXTURE)
        assert suite.tasks[1].metadata == {}

    def test_metadata_empty_dict_when_explicitly_empty(self) -> None:
        # task s3 has "metadata": {}
        suite = Suite.from_jsonl(_FIXTURE)
        assert suite.tasks[2].metadata == {}

    def test_default_name_from_stem(self) -> None:
        suite = Suite.from_jsonl(_FIXTURE)
        assert suite.name == "sample"

    def test_explicit_name_overrides_stem(self) -> None:
        suite = Suite.from_jsonl(_FIXTURE, name="custom-name")
        assert suite.name == "custom-name"

    def test_blank_lines_skipped(self) -> None:
        # the fixture file has one blank line between s2 and s3
        suite = Suite.from_jsonl(_FIXTURE)
        assert len(suite.tasks) == 3  # not 4

    def test_raises_key_error_on_missing_required_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.jsonl"
        bad.write_text('{"task_id": "t1", "input": "x"}\n', encoding="utf-8")
        with pytest.raises(KeyError):
            Suite.from_jsonl(bad)


# ---------------------------------------------------------------------------
# T2: arithmetic suite — shape
# ---------------------------------------------------------------------------


class TestArithmeticSuiteShape:
    def test_task_count(self) -> None:
        assert len(arithmetic_suite().tasks) == 50

    def test_suite_name(self) -> None:
        assert arithmetic_suite().name == "arithmetic"

    def test_all_task_ids_unique(self) -> None:
        tasks = arithmetic_suite().tasks
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))

    def test_expected_outputs_are_digit_strings(self) -> None:
        for task in arithmetic_suite().tasks:
            # expected_output should be a valid integer string (possibly negative)
            int(task.expected_output)  # raises ValueError if not

    def test_eval_matches_expected(self) -> None:
        for task in arithmetic_suite().tasks:
            computed = str(eval(task.input))  # noqa: S307
            assert computed == task.expected_output, (
                f"task {task.task_id}: eval({task.input!r}) = {computed!r} "
                f"but expected {task.expected_output!r}"
            )


# ---------------------------------------------------------------------------
# T3: arithmetic agent
# ---------------------------------------------------------------------------


class TestArithmeticAgent:
    def test_addition(self) -> None:
        assert asyncio.run(arithmetic_agent("2+2")) == "4"

    def test_multiplication(self) -> None:
        assert asyncio.run(arithmetic_agent("7*8")) == "56"

    def test_integer_division(self) -> None:
        assert asyncio.run(arithmetic_agent("81//9")) == "9"

    def test_modulo(self) -> None:
        assert asyncio.run(arithmetic_agent("7%3")) == "1"

    def test_subtraction(self) -> None:
        assert asyncio.run(arithmetic_agent("100-45")) == "55"

    def test_returns_string(self) -> None:
        result = asyncio.run(arithmetic_agent("3*4"))
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# T4: arithmetic end-to-end
# ---------------------------------------------------------------------------


class TestArithmeticEndToEnd:
    def test_success_rate_is_one(self) -> None:
        runner = BenchmarkRunner(agent_fn=arithmetic_agent)
        report = asyncio.run(runner.run(arithmetic_suite()))
        assert report.success_rate == pytest.approx(1.0)
        assert len(report.task_results) == 50


# ---------------------------------------------------------------------------
# T5: qa_lookup suite — shape
# ---------------------------------------------------------------------------


class TestQaLookupSuiteShape:
    def test_task_count(self) -> None:
        assert len(qa_lookup_suite().tasks) == 30

    def test_suite_name(self) -> None:
        assert qa_lookup_suite().name == "qa_lookup"

    def test_all_task_ids_unique(self) -> None:
        ids = [t.task_id for t in qa_lookup_suite().tasks]
        assert len(ids) == len(set(ids))

    def test_all_inputs_non_empty(self) -> None:
        for task in qa_lookup_suite().tasks:
            assert task.input.strip()

    def test_all_expected_outputs_non_empty(self) -> None:
        for task in qa_lookup_suite().tasks:
            assert task.expected_output.strip()


# ---------------------------------------------------------------------------
# T6: qa_lookup agent
# ---------------------------------------------------------------------------


class TestQaLookupAgent:
    def test_capital_of_france(self) -> None:
        assert asyncio.run(qa_lookup_agent("capital of france")) == "Paris"

    def test_chemical_symbol_gold(self) -> None:
        assert asyncio.run(qa_lookup_agent("chemical symbol for gold")) == "Au"

    def test_bits_in_byte(self) -> None:
        assert asyncio.run(qa_lookup_agent("bits in a byte")) == "8"

    def test_unknown_returns_unknown(self) -> None:
        assert asyncio.run(qa_lookup_agent("this is not a real question")) == "unknown"

    def test_strips_whitespace(self) -> None:
        assert asyncio.run(qa_lookup_agent("  capital of france  ")) == "Paris"


# ---------------------------------------------------------------------------
# T7: qa_lookup end-to-end
# ---------------------------------------------------------------------------


class TestQaLookupEndToEnd:
    def test_success_rate_is_one(self) -> None:
        runner = BenchmarkRunner(agent_fn=qa_lookup_agent)
        report = asyncio.run(runner.run(qa_lookup_suite()))
        assert report.success_rate == pytest.approx(1.0)
        assert len(report.task_results) == 30


# ---------------------------------------------------------------------------
# T8: hallucination suite — shape
# ---------------------------------------------------------------------------


class TestHallucinationSuiteShape:
    def test_task_count(self) -> None:
        assert len(hallucination_suite().tasks) == 25

    def test_suite_name(self) -> None:
        assert hallucination_suite().name == "hallucination"

    def test_all_inputs_contain_passage_and_claim(self) -> None:
        for task in hallucination_suite().tasks:
            assert "PASSAGE:" in task.input
            assert "CLAIM:" in task.input

    def test_all_expected_outputs_are_valid_labels(self) -> None:
        valid = {"supported", "not_supported"}
        for task in hallucination_suite().tasks:
            assert task.expected_output in valid, (
                f"{task.task_id}: unexpected label {task.expected_output!r}"
            )

    def test_both_labels_present(self) -> None:
        labels = {t.expected_output for t in hallucination_suite().tasks}
        assert labels == {"supported", "not_supported"}


# ---------------------------------------------------------------------------
# T9: hallucination agent
# ---------------------------------------------------------------------------


class TestHallucinationAgent:
    def test_supported_claim(self) -> None:
        inp = "PASSAGE: Paris is the capital of France.\nCLAIM: Paris is the capital of France."
        assert asyncio.run(hallucination_agent(inp)) == "supported"

    def test_unsupported_claim(self) -> None:
        inp = "PASSAGE: Paris is the capital of France.\nCLAIM: Dolphins are marine mammals."
        assert asyncio.run(hallucination_agent(inp)) == "not_supported"

    def test_malformed_input_returns_not_supported(self) -> None:
        # No CLAIM section
        assert asyncio.run(hallucination_agent("just some text")) == "not_supported"

    def test_identical_claim_and_passage(self) -> None:
        text = "Water boils at 100 degrees Celsius."
        inp = f"PASSAGE: {text}\nCLAIM: {text}"
        assert asyncio.run(hallucination_agent(inp)) == "supported"


# ---------------------------------------------------------------------------
# T10: hallucination end-to-end
# ---------------------------------------------------------------------------


class TestHallucinationEndToEnd:
    def test_success_rate_is_one(self) -> None:
        runner = BenchmarkRunner(agent_fn=hallucination_agent)
        report = asyncio.run(runner.run(hallucination_suite()))
        assert report.success_rate == pytest.approx(1.0), "Failing tasks: " + str(
            [r.task_id for r in report.task_results if not r.success]
        )
        assert len(report.task_results) == 25


# ---------------------------------------------------------------------------
# T11: classification suite — shape
# ---------------------------------------------------------------------------


class TestClassificationSuiteShape:
    def test_task_count(self) -> None:
        assert len(classification_suite().tasks) == 20

    def test_suite_name(self) -> None:
        assert classification_suite().name == "classification"

    def test_all_task_ids_unique(self) -> None:
        ids = [t.task_id for t in classification_suite().tasks]
        assert len(ids) == len(set(ids))

    def test_all_expected_outputs_are_valid_labels(self) -> None:
        for task in classification_suite().tasks:
            assert task.expected_output in {"positive", "negative"}

    def test_both_labels_present(self) -> None:
        labels = {t.expected_output for t in classification_suite().tasks}
        assert labels == {"positive", "negative"}


# ---------------------------------------------------------------------------
# T12: classification agent
# ---------------------------------------------------------------------------


class TestClassificationAgent:
    def test_positive_text(self) -> None:
        result = asyncio.run(classification_agent("This product is excellent and amazing."))
        assert result == "positive"

    def test_negative_text(self) -> None:
        result = asyncio.run(classification_agent("Terrible quality and completely useless."))
        assert result == "negative"

    def test_tie_returns_positive(self) -> None:
        # equal positive and negative counts → returns "positive" (>= branch)
        result = asyncio.run(classification_agent("excellent terrible"))
        assert result == "positive"

    def test_no_keywords_returns_positive(self) -> None:
        # zero pos, zero neg → 0 >= 0 → "positive"
        result = asyncio.run(classification_agent("the weather is fine today"))
        assert result == "positive"

    def test_returns_string(self) -> None:
        result = asyncio.run(classification_agent("some text"))
        assert isinstance(result, str)

    def test_word_sets_are_disjoint(self) -> None:
        """Positive and negative word sets must not overlap."""
        assert _POSITIVE_WORDS.isdisjoint(_NEGATIVE_WORDS)


# ---------------------------------------------------------------------------
# T13: classification end-to-end
# ---------------------------------------------------------------------------


class TestClassificationEndToEnd:
    def test_success_rate_is_one(self) -> None:
        runner = BenchmarkRunner(agent_fn=classification_agent)
        report = asyncio.run(runner.run(classification_suite()))
        assert report.success_rate == pytest.approx(1.0), "Failing tasks: " + str(
            [r.task_id for r in report.task_results if not r.success]
        )
        assert len(report.task_results) == 20


# ---------------------------------------------------------------------------
# T14: BUILTIN_SUITES registry
# ---------------------------------------------------------------------------


class TestBuiltinSuitesRegistry:
    _EXPECTED_KEYS = {"tiny", "arithmetic", "qa_lookup", "hallucination", "classification"}

    def test_has_expected_keys(self) -> None:
        assert set(BUILTIN_SUITES.keys()) == self._EXPECTED_KEYS

    def test_all_values_are_suite_instances(self) -> None:
        for name, suite in BUILTIN_SUITES.items():
            assert isinstance(suite, Suite), f"BUILTIN_SUITES[{name!r}] is not a Suite"

    def test_suite_names_match_keys(self) -> None:
        for key, suite in BUILTIN_SUITES.items():
            assert suite.name == key, f"BUILTIN_SUITES[{key!r}].name = {suite.name!r} (mismatch)"

    def test_all_suites_non_empty(self) -> None:
        for key, suite in BUILTIN_SUITES.items():
            assert len(suite.tasks) > 0, f"BUILTIN_SUITES[{key!r}] has no tasks"


# ---------------------------------------------------------------------------
# T15: BUILTIN_AGENTS registry
# ---------------------------------------------------------------------------


class TestBuiltinAgentsRegistry:
    def test_keys_match_suites(self) -> None:
        assert set(BUILTIN_AGENTS.keys()) == set(BUILTIN_SUITES.keys())

    def test_all_values_are_callable(self) -> None:
        for name, agent in BUILTIN_AGENTS.items():
            assert callable(agent), f"BUILTIN_AGENTS[{name!r}] is not callable"

    def test_all_agents_are_coroutine_functions(self) -> None:
        import asyncio as _asyncio

        for name, agent_fn in BUILTIN_AGENTS.items():
            # agent must return a coroutine when called with a dummy string
            coro = agent_fn("test")
            assert _asyncio.iscoroutine(coro), (
                f"BUILTIN_AGENTS[{name!r}] did not return a coroutine"
            )
            coro.close()  # clean up without awaiting


# ---------------------------------------------------------------------------
# T16: __init__.py export
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_builtin_suites_importable_from_package(self) -> None:
        from llm_agents.evaluation.benchmarking import BUILTIN_SUITES as bs  # noqa: PLC0415

        assert isinstance(bs, dict)
        assert len(bs) >= 5

    def test_builtin_agents_importable_from_package(self) -> None:
        from llm_agents.evaluation.benchmarking import BUILTIN_AGENTS as ba  # noqa: PLC0415

        assert isinstance(ba, dict)
        assert len(ba) >= 5


# ---------------------------------------------------------------------------
# T17: CLI --suite all
# ---------------------------------------------------------------------------


class TestCLISuiteAll:
    def test_suite_all_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--suite", "all"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_suite_all_returns_valid_json_list(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--suite", "all"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_suite_all_has_five_entries(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--suite", "all"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        assert len(data) == 5

    def test_suite_all_every_suite_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "llm_agents.evaluation.benchmarking", "--suite", "all"],
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        for entry in data:
            assert entry["success_rate"] == pytest.approx(1.0), (
                f"Suite {entry['suite_name']!r} had success_rate={entry['success_rate']}"
            )
