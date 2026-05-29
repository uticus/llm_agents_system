"""Unit tests for infra/guardrails.

Covers GuardResult constructors, Guard protocol, RegexFilter, KeywordFilter,
RedactFilter, EmbeddingFilter, GuardrailChain (PASS/BLOCK/REDACT paths,
short-circuit, and on_violation callback).
No real model or network calls.
"""

from __future__ import annotations

import re

from llm_agents.infra.guardrails import (
    EmbeddingFilter,
    Guard,
    GuardAction,
    GuardrailChain,
    GuardResult,
    KeywordFilter,
    RedactFilter,
    RegexFilter,
)

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_guard_result_pass():
    """GuardResult.pass_() sets passed=True and action=PASS."""
    r = GuardResult.pass_("hello")
    assert r.passed is True
    assert r.action == GuardAction.PASS
    assert r.text == "hello"
    assert r.violation_detail is None


def test_guard_result_block():
    """GuardResult.block() sets passed=False and action=BLOCK."""
    r = GuardResult.block("bad text", "policy violation")
    assert r.passed is False
    assert r.action == GuardAction.BLOCK
    assert r.violation_detail == "policy violation"


def test_guard_result_redact():
    """GuardResult.redact() sets passed=False and action=REDACT."""
    r = GuardResult.redact("[REDACTED]", "sensitive removed")
    assert r.passed is False
    assert r.action == GuardAction.REDACT
    assert "[REDACTED]" in r.text


# ---------------------------------------------------------------------------
# T1: RegexFilter
# ---------------------------------------------------------------------------


def test_regex_filter_pass():
    """T1: RegexFilter passes text that does not match any pattern."""
    f = RegexFilter([r"\bpassword\b"])
    result = f.check("my secret is hidden")
    assert result.passed is True


def test_regex_filter_block():
    """T1b: RegexFilter blocks text that matches a pattern."""
    f = RegexFilter([r"\bpassword\b"])
    result = f.check("please enter your password here")
    assert result.passed is False
    assert result.action == GuardAction.BLOCK
    assert "password" in (result.violation_detail or "")


def test_regex_filter_multiple_patterns():
    """T1c: RegexFilter blocks on first matching pattern."""
    f = RegexFilter([r"\bsecret\b", r"\btoken\b"])
    assert f.check("no violation").passed is True
    assert not f.check("the secret is safe").passed
    assert not f.check("bearer token included").passed


def test_regex_filter_case_insensitive():
    """T1d: RegexFilter respects provided flags (case-insensitive)."""
    f = RegexFilter([r"password"], flags=re.IGNORECASE)
    assert not f.check("Enter your PASSWORD").passed


# ---------------------------------------------------------------------------
# T2: KeywordFilter
# ---------------------------------------------------------------------------


def test_keyword_filter_pass():
    """T2: KeywordFilter passes text with no matching keywords."""
    f = KeywordFilter(["secret", "confidential"])
    assert f.check("this is public information").passed is True


def test_keyword_filter_block():
    """T2b: KeywordFilter blocks text containing a keyword."""
    f = KeywordFilter(["secret"])
    result = f.check("this is a SECRET project")
    assert result.passed is False
    assert result.action == GuardAction.BLOCK


def test_keyword_filter_case_insensitive():
    """T2c: KeywordFilter matching is case-insensitive."""
    f = KeywordFilter(["forbidden"])
    assert not f.check("FORBIDDEN content").passed
    assert not f.check("forbidden content").passed


# ---------------------------------------------------------------------------
# T3: RedactFilter
# ---------------------------------------------------------------------------


def test_redact_filter_pass():
    """T3: RedactFilter passes and returns unchanged text when no match."""
    f = RedactFilter([r"\bSSN:\s*\d{3}-\d{2}-\d{4}\b"])
    result = f.check("no sensitive info here")
    assert result.passed is True
    assert result.text == "no sensitive info here"


def test_redact_filter_redacts():
    """T3b: RedactFilter replaces matched text and returns REDACT."""
    f = RedactFilter([r"\bSSN:\s*\d{3}-\d{2}-\d{4}\b"])
    result = f.check("Your SSN: 123-45-6789 is on file.")
    assert result.action == GuardAction.REDACT
    assert "[REDACTED]" in result.text
    assert "123-45-6789" not in result.text


def test_redact_filter_multiple_occurrences():
    """T3c: RedactFilter replaces all occurrences."""
    f = RedactFilter([r"\bemail\b"], flags=re.IGNORECASE)
    result = f.check("Send email to this email address.")
    assert result.text.count("[REDACTED]") == 2


def test_redact_filter_custom_marker():
    """T3d: RedactFilter uses the provided marker string."""
    f = RedactFilter([r"secret"], marker="***")
    result = f.check("the secret is out")
    assert "***" in result.text


# ---------------------------------------------------------------------------
# T4: EmbeddingFilter
# ---------------------------------------------------------------------------


def test_embedding_filter_pass():
    """T4: EmbeddingFilter passes when scorer returns value >= threshold."""
    scorer = lambda text: 0.8  # noqa: E731
    f = EmbeddingFilter(scorer=scorer, threshold=0.5)
    result = f.check("on-domain text")
    assert result.passed is True


def test_embedding_filter_block():
    """T4b: EmbeddingFilter blocks when scorer returns value < threshold."""
    scorer = lambda text: 0.3  # noqa: E731
    f = EmbeddingFilter(scorer=scorer, threshold=0.5)
    result = f.check("off-domain text")
    assert result.passed is False
    assert result.action == GuardAction.BLOCK
    assert "0.300" in (result.violation_detail or "")


def test_embedding_filter_at_threshold():
    """T4c: EmbeddingFilter passes at exactly the threshold."""
    scorer = lambda text: 0.5  # noqa: E731
    f = EmbeddingFilter(scorer=scorer, threshold=0.5)
    assert f.check("borderline text").passed is True


# ---------------------------------------------------------------------------
# T5: Guard protocol
# ---------------------------------------------------------------------------


def test_guard_protocol_regex():
    """T5: RegexFilter satisfies the Guard protocol."""
    assert isinstance(RegexFilter([r"x"]), Guard)


def test_guard_protocol_keyword():
    """T5b: KeywordFilter satisfies the Guard protocol."""
    assert isinstance(KeywordFilter(["x"]), Guard)


def test_guard_protocol_redact():
    """T5c: RedactFilter satisfies the Guard protocol."""
    assert isinstance(RedactFilter([r"x"]), Guard)


def test_guard_protocol_embedding():
    """T5d: EmbeddingFilter satisfies the Guard protocol."""
    assert isinstance(EmbeddingFilter(scorer=lambda t: 1.0), Guard)


# ---------------------------------------------------------------------------
# T6: GuardrailChain
# ---------------------------------------------------------------------------


def test_chain_pass_all():
    """T6: Chain returns PASS when all guards pass."""
    chain = GuardrailChain([
        KeywordFilter(["bad"]),
        RegexFilter([r"\bforbidden\b"]),
    ])
    result = chain.run("this is fine text")
    assert result.passed is True


def test_chain_block_on_first_violation():
    """T6b: Chain returns BLOCK at the first blocking guard."""
    violations: list = []
    chain = GuardrailChain(
        [
            KeywordFilter(["block_me"]),
            RegexFilter([r"should_not_reach"]),
        ],
        on_violation=violations.append,
    )
    result = chain.run("please block_me now")
    assert result.passed is False
    assert result.action == GuardAction.BLOCK
    assert len(violations) == 1


def test_chain_redact_stops_chain():
    """T6c: REDACT result stops the chain."""
    second_guard_called = [False]

    class _TrackingGuard:
        def check(self, text: str) -> GuardResult:
            second_guard_called[0] = True
            return GuardResult.pass_(text)

    chain = GuardrailChain([
        RedactFilter([r"secret"]),
        _TrackingGuard(),
    ])
    result = chain.run("the secret key is here")
    assert result.action == GuardAction.REDACT
    assert second_guard_called[0] is False, "Chain must stop at REDACT"


def test_chain_empty_guards():
    """T6d: Empty chain always returns PASS."""
    chain = GuardrailChain([])
    result = chain.run("anything")
    assert result.passed is True


def test_chain_on_violation_called_for_redact():
    """T6e: on_violation callback is called for REDACT results too."""
    violations: list = []
    chain = GuardrailChain(
        [RedactFilter([r"pii"])],
        on_violation=violations.append,
    )
    chain.run("remove pii here")
    assert len(violations) == 1
    assert violations[0].action == GuardAction.REDACT


def test_chain_on_violation_not_called_for_pass():
    """T6f: on_violation is NOT called when all guards pass."""
    violations: list = []
    chain = GuardrailChain(
        [KeywordFilter(["bad"])],
        on_violation=violations.append,
    )
    chain.run("totally fine text")
    assert violations == []
