"""Unit tests for core/prompting: PromptTemplate, FewShotTemplate, ExampleSelector."""

from __future__ import annotations

import pytest

from llm_agents.core.prompting import (
    Example,
    ExampleSelector,
    FewShotTemplate,
    PromptTemplate,
)


# ---------------------------------------------------------------------------
# PromptTemplate
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    def test_simple_format(self) -> None:
        tmpl = PromptTemplate("Hello, {name}!")
        assert tmpl.format(name="Alice") == "Hello, Alice!"

    def test_multi_placeholder(self) -> None:
        tmpl = PromptTemplate("{a} + {b} = {c}")
        assert tmpl.format(a="1", b="2", c="3") == "1 + 2 = 3"

    def test_missing_placeholder_raises(self) -> None:
        tmpl = PromptTemplate("Hello, {name}!")
        with pytest.raises(KeyError):
            tmpl.format()

    def test_no_placeholders(self) -> None:
        tmpl = PromptTemplate("Static text")
        assert tmpl.format() == "Static text"

    def test_variables_property(self) -> None:
        tmpl = PromptTemplate("{a} and {b} and {a} again")
        assert tmpl.variables == ["a", "b"]

    def test_variables_empty(self) -> None:
        tmpl = PromptTemplate("no vars here")
        assert tmpl.variables == []

    def test_variables_order(self) -> None:
        tmpl = PromptTemplate("{z} {y} {x}")
        assert tmpl.variables == ["z", "y", "x"]

    def test_metadata_default_empty(self) -> None:
        tmpl = PromptTemplate("x")
        assert tmpl.metadata == {}

    def test_metadata_stored(self) -> None:
        tmpl = PromptTemplate("x", metadata={"version": "1"})
        assert tmpl.metadata == {"version": "1"}

    def test_extra_kwargs_ignored_via_format_map(self) -> None:
        tmpl = PromptTemplate("{a}")
        # format_map uses a dict and ignores extra keys — no error
        assert tmpl.format(a="1", b="2") == "1"


# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------


class TestExample:
    def test_construction(self) -> None:
        ex = Example(input_text="in", output_text="out")
        assert ex.input_text == "in"
        assert ex.output_text == "out"


# ---------------------------------------------------------------------------
# FewShotTemplate
# ---------------------------------------------------------------------------


class TestFewShotTemplate:
    def test_no_examples(self) -> None:
        tmpl = FewShotTemplate("Do the task.")
        result = tmpl.format("my query")
        assert "Do the task." in result
        assert "my query" in result

    def test_with_examples(self) -> None:
        ex = Example("2+2", "4")
        tmpl = FewShotTemplate("Math assistant.", examples=[ex])
        result = tmpl.format("3+3")
        assert "2+2" in result
        assert "4" in result
        assert "3+3" in result

    def test_custom_labels(self) -> None:
        ex = Example("hello", "bonjour")
        tmpl = FewShotTemplate(
            "Translate.",
            examples=[ex],
            input_label="EN",
            output_label="FR",
            query_label="EN",
        )
        result = tmpl.format("world")
        assert "EN: hello" in result
        assert "FR: bonjour" in result

    def test_separator(self) -> None:
        ex = Example("a", "b")
        tmpl = FewShotTemplate("Instr.", examples=[ex], separator="---")
        result = tmpl.format("q")
        assert "---" in result

    def test_default_separator_is_double_newline(self) -> None:
        tmpl = FewShotTemplate("Instr.")
        result = tmpl.format("q")
        assert "\n\n" in result

    def test_multiple_examples_all_present(self) -> None:
        examples = [Example(f"in{i}", f"out{i}") for i in range(3)]
        tmpl = FewShotTemplate("Task.", examples=examples)
        result = tmpl.format("final")
        for i in range(3):
            assert f"in{i}" in result
            assert f"out{i}" in result

    def test_output_label_at_end(self) -> None:
        tmpl = FewShotTemplate("Task.", output_label="Answer")
        result = tmpl.format("q")
        # The last part should end with "Answer:" (the prompt for generation)
        assert result.endswith("Answer:")


# ---------------------------------------------------------------------------
# ExampleSelector
# ---------------------------------------------------------------------------


class TestExampleSelector:
    def _make_examples(self, n: int = 5) -> list[Example]:
        return [Example(f"input{i}", f"output{i}") for i in range(n)]

    def test_returns_top_k(self) -> None:
        examples = self._make_examples(10)
        # scorer prefers examples with higher index
        selector = ExampleSelector(
            examples,
            scorer=lambda q, ex: int(ex.input_text[5:]),
            top_k=3,
        )
        result = selector.select("anything")
        assert len(result) == 3

    def test_sorted_by_score_descending(self) -> None:
        examples = [Example(f"{i}", f"{i}") for i in range(5)]
        scores = {ex.input_text: float(ex.input_text) for ex in examples}
        selector = ExampleSelector(
            examples,
            scorer=lambda q, ex: scores[ex.input_text],
            top_k=5,
        )
        result = selector.select("q")
        assert [r.input_text for r in result] == ["4", "3", "2", "1", "0"]

    def test_per_call_top_k_override(self) -> None:
        examples = self._make_examples(5)
        selector = ExampleSelector(examples, scorer=lambda q, ex: 1.0, top_k=5)
        result = selector.select("q", top_k=2)
        assert len(result) == 2

    def test_empty_pool_returns_empty(self) -> None:
        selector = ExampleSelector([], scorer=lambda q, ex: 1.0, top_k=3)
        assert selector.select("q") == []

    def test_top_k_larger_than_pool(self) -> None:
        examples = self._make_examples(2)
        selector = ExampleSelector(examples, scorer=lambda q, ex: 1.0, top_k=10)
        result = selector.select("q")
        assert len(result) == 2

    def test_scorer_receives_query(self) -> None:
        received: list[str] = []
        ex = Example("x", "y")

        def scorer(query, example):
            received.append(query)
            return 1.0

        selector = ExampleSelector([ex], scorer=scorer, top_k=1)
        selector.select("my query")
        assert received == ["my query"]

    def test_does_not_mutate_pool(self) -> None:
        examples = self._make_examples(3)
        original_ids = [ex.input_text for ex in examples]
        selector = ExampleSelector(examples, scorer=lambda q, ex: 1.0, top_k=3)
        selector.select("q")
        assert [ex.input_text for ex in examples] == original_ids
