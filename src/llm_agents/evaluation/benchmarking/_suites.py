"""Concrete benchmark task suites with paired deterministic agents.

Each suite is fully self-contained: no optional extras, no network calls, no
disk access.  Every suite is paired with an async agent function that is
designed to answer every task correctly, so the expected success rate when
using the paired agent is 1.0 (100 %).

Exported names
--------------
- :func:`arithmetic_suite` / :func:`arithmetic_agent`
- :func:`qa_lookup_suite` / :func:`qa_lookup_agent`
- :func:`hallucination_suite` / :func:`hallucination_agent`
- :func:`classification_suite` / :func:`classification_agent`
- :data:`BUILTIN_SUITES` — ``dict[str, Suite]``
- :data:`BUILTIN_AGENTS` — ``dict[str, AsyncAgent]``

[WARNING] The arithmetic and qa_lookup agents use ``eval()`` and dict lookup
on controlled, pre-defined input strings only.  Never pass untrusted input to
these agents.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from llm_agents.evaluation.benchmarking._models import BenchmarkTask, Suite

AsyncAgent = Callable[[str], Coroutine[Any, Any, Any]]

# ---------------------------------------------------------------------------
# Suite 0: tiny (backward-compatible demo suite)
# ---------------------------------------------------------------------------

_TINY_ANSWERS: dict[str, str] = {"2+2": "4", "3*3": "9", "10-1": "9"}


def _build_tiny_suite() -> Suite:
    """Return the three-task demonstration suite used by the CLI smoke test."""
    return Suite(
        name="tiny",
        tasks=[
            BenchmarkTask(task_id="t1", input="2+2", expected_output="4"),
            BenchmarkTask(task_id="t2", input="3*3", expected_output="9"),
            BenchmarkTask(task_id="t3", input="10-1", expected_output="9"),
        ],
    )


async def _tiny_agent(input_text: str) -> str:  # noqa: RUF029
    return _TINY_ANSWERS.get(input_text, "")


# ---------------------------------------------------------------------------
# Suite 1: arithmetic — 50 tasks across five operation types
# ---------------------------------------------------------------------------

# fmt: off
_ARITHMETIC_TASKS: list[tuple[str, str, str]] = [
    # (task_id, expression, expected_str)
    # Additions
    ("arith-add-01", "2+2",       "4"),
    ("arith-add-02", "3+7",       "10"),
    ("arith-add-03", "15+23",     "38"),
    ("arith-add-04", "100+250",   "350"),
    ("arith-add-05", "8+12",      "20"),
    ("arith-add-06", "17+43",     "60"),
    ("arith-add-07", "6+94",      "100"),
    ("arith-add-08", "50+50",     "100"),
    ("arith-add-09", "11+99",     "110"),
    ("arith-add-10", "37+48",     "85"),
    # Subtractions
    ("arith-sub-01", "10-3",      "7"),
    ("arith-sub-02", "100-45",    "55"),
    ("arith-sub-03", "50-20",     "30"),
    ("arith-sub-04", "7-7",       "0"),
    ("arith-sub-05", "99-1",      "98"),
    ("arith-sub-06", "200-100",   "100"),
    ("arith-sub-07", "88-8",      "80"),
    ("arith-sub-08", "36-9",      "27"),
    ("arith-sub-09", "15-7",      "8"),
    ("arith-sub-10", "1000-1",    "999"),
    # Multiplications
    ("arith-mul-01", "3*4",       "12"),
    ("arith-mul-02", "5*6",       "30"),
    ("arith-mul-03", "7*8",       "56"),
    ("arith-mul-04", "2*9",       "18"),
    ("arith-mul-05", "10*11",     "110"),
    ("arith-mul-06", "12*3",      "36"),
    ("arith-mul-07", "4*4",       "16"),
    ("arith-mul-08", "6*7",       "42"),
    ("arith-mul-09", "9*9",       "81"),
    ("arith-mul-10", "15*4",      "60"),
    # Integer divisions
    ("arith-div-01", "12//4",     "3"),
    ("arith-div-02", "100//10",   "10"),
    ("arith-div-03", "81//9",     "9"),
    ("arith-div-04", "56//7",     "8"),
    ("arith-div-05", "144//12",   "12"),
    ("arith-div-06", "50//5",     "10"),
    ("arith-div-07", "36//6",     "6"),
    ("arith-div-08", "64//8",     "8"),
    ("arith-div-09", "72//9",     "8"),
    ("arith-div-10", "90//10",    "9"),
    # Modulo
    ("arith-mod-01", "7%3",       "1"),
    ("arith-mod-02", "10%4",      "2"),
    ("arith-mod-03", "17%5",      "2"),
    ("arith-mod-04", "23%7",      "2"),
    ("arith-mod-05", "100%9",     "1"),
    ("arith-mod-06", "55%8",      "7"),
    ("arith-mod-07", "31%6",      "1"),
    ("arith-mod-08", "44%11",     "0"),
    ("arith-mod-09", "77%7",      "0"),
    ("arith-mod-10", "99%10",     "9"),
]
# fmt: on


def arithmetic_suite() -> Suite:
    """Return the 50-task arithmetic benchmark suite."""
    tasks = [
        BenchmarkTask(task_id=tid, input=expr, expected_output=exp)
        for tid, expr, exp in _ARITHMETIC_TASKS
    ]
    return Suite(name="arithmetic", tasks=tasks)


async def arithmetic_agent(input_text: str) -> str:  # noqa: RUF029
    """Evaluate a Python arithmetic expression and return the string result.

    [WARNING] Only call with trusted, pre-defined expressions from the suite.
    """
    # eval is safe here: inputs are pre-defined constants from _ARITHMETIC_TASKS.
    return str(eval(input_text))  # noqa: S307


# ---------------------------------------------------------------------------
# Suite 2: qa_lookup — 30 factual Q&A pairs
# ---------------------------------------------------------------------------

# fmt: off
_QA_ANSWERS: dict[str, str] = {
    # Geography (6)
    "capital of france":               "Paris",
    "capital of germany":              "Berlin",
    "capital of japan":                "Tokyo",
    "capital of australia":            "Canberra",
    "capital of brazil":               "Brasilia",
    "capital of canada":               "Ottawa",
    # Chemistry (5)
    "chemical symbol for gold":        "Au",
    "chemical symbol for silver":      "Ag",
    "chemical symbol for iron":        "Fe",
    "chemical symbol for oxygen":      "O",
    "chemical symbol for carbon":      "C",
    # Physics (5)
    "boiling point of water celsius":  "100",
    "freezing point of water celsius": "0",
    "absolute zero celsius":           "-273",
    "planets in the solar system":     "8",
    "speed of light m/s":              "299792458",
    # Mathematics (6)
    "pi to two decimal places":        "3.14",
    "square root of 144":              "12",
    "square root of 256":              "16",
    "factorial of 5":                  "120",
    "factorial of 6":                  "720",
    "fibonacci 10th number":           "55",
    # Computing (5)
    "bits in a byte":                  "8",
    "bytes in a kilobyte":             "1024",
    "base of binary":                  "2",
    "base of hexadecimal":             "16",
    "http default port":               "80",
    # History and culture (3)
    "year world war 2 ended":          "1945",
    "year of first moon landing":      "1969",
    "year eiffel tower built":         "1889",
}
# fmt: on


def qa_lookup_suite() -> Suite:
    """Return the 30-task factual Q&A benchmark suite."""
    tasks = [
        BenchmarkTask(
            task_id=f"qa-{i:02d}",
            input=question,
            expected_output=answer,
        )
        for i, (question, answer) in enumerate(_QA_ANSWERS.items())
    ]
    return Suite(name="qa_lookup", tasks=tasks)


async def qa_lookup_agent(input_text: str) -> str:  # noqa: RUF029
    """Return the answer for *input_text* from the built-in knowledge base."""
    return _QA_ANSWERS.get(input_text.strip().lower(), "unknown")


# ---------------------------------------------------------------------------
# Suite 3: hallucination — 25 passage/claim verification tasks
#
# Task format:  "PASSAGE: <text>\nCLAIM: <claim>"
# Expected:     "supported" | "not_supported"
#
# The agent uses OverlapDetector(threshold=0.5) from evaluation.hallucination.
# Token-overlap scores for each task are computed as:
#   score = |unique(claim_tokens) ∩ unique(passage_tokens)| / |unique(claim_tokens)|
# "Supported" tasks score ≥ 0.80; "not_supported" tasks score ≤ 0.20.
# ---------------------------------------------------------------------------

def _hp(passage: str, claim: str) -> str:
    """Format a passage+claim input string."""
    return f"PASSAGE: {passage}\nCLAIM: {claim}"


# fmt: off
_HALLUCINATION_TASKS: list[tuple[str, str, str]] = [
    # (task_id, input, expected_output)

    # Supported — claim tokens are a near-complete subset of passage tokens
    ("hall-sup-01",
     _hp("The Eiffel Tower is located in Paris, France.",
         "The Eiffel Tower is in Paris."),
     "supported"),
    ("hall-sup-02",
     _hp("Water boils at one hundred degrees Celsius at sea level.",
         "Water boils at one hundred degrees Celsius."),
     "supported"),
    ("hall-sup-03",
     _hp("Jupiter is the largest planet in our solar system.",
         "Jupiter is the largest planet in the solar system."),
     "supported"),
    ("hall-sup-04",
     _hp("Shakespeare wrote Hamlet and Macbeth among other famous plays.",
         "Shakespeare wrote Hamlet."),
     "supported"),
    ("hall-sup-05",
     _hp("The speed of light in a vacuum is approximately three hundred "
         "million meters per second.",
         "The speed of light is approximately three hundred million meters per second."),
     "supported"),
    ("hall-sup-06",
     _hp("The Python programming language was created by Guido van Rossum.",
         "Python was created by Guido van Rossum."),
     "supported"),
    ("hall-sup-07",
     _hp("DNA carries genetic information in all living organisms.",
         "DNA carries genetic information in living organisms."),
     "supported"),
    ("hall-sup-08",
     _hp("The Amazon River is the largest river by discharge in the world.",
         "The Amazon River is the largest river by discharge."),
     "supported"),
    ("hall-sup-09",
     _hp("Neil Armstrong was the first human to walk on the Moon in nineteen sixty-nine.",
         "Neil Armstrong was the first human to walk on the Moon."),
     "supported"),
    ("hall-sup-10",
     _hp("Mount Everest is the highest mountain above sea level on Earth.",
         "Mount Everest is the highest mountain on Earth."),
     "supported"),
    ("hall-sup-11",
     _hp("The human body has two hundred and six bones in adults.",
         "The human body has two hundred and six bones."),
     "supported"),
    ("hall-sup-12",
     _hp("Photosynthesis is the process by which plants convert sunlight into energy.",
         "Photosynthesis is the process by which plants convert sunlight into energy."),
     "supported"),

    # Not supported — claim vocabulary is entirely distinct from passage vocabulary
    ("hall-nsp-01",
     _hp("The Eiffel Tower is located in Paris, France.",
         "Dolphins are highly intelligent marine mammals."),
     "not_supported"),
    ("hall-nsp-02",
     _hp("Water freezes at zero degrees Celsius.",
         "Quantum computers use qubits to process information."),
     "not_supported"),
    ("hall-nsp-03",
     _hp("Jupiter is the largest planet in our solar system.",
         "Baking bread requires flour, water, and yeast."),
     "not_supported"),
    ("hall-nsp-04",
     _hp("Shakespeare wrote Hamlet and Macbeth.",
         "The Great Wall of China stretches thousands of kilometers."),
     "not_supported"),
    ("hall-nsp-05",
     _hp("DNA carries genetic information in living organisms.",
         "Electric vehicles reduce carbon emissions in cities."),
     "not_supported"),
    ("hall-nsp-06",
     _hp("The Amazon River is the largest river by discharge in the world.",
         "Robots are increasingly used in manufacturing processes."),
     "not_supported"),
    ("hall-nsp-07",
     _hp("Mount Everest is the highest mountain above sea level on Earth.",
         "Machine learning algorithms improve with more training data."),
     "not_supported"),
    ("hall-nsp-08",
     _hp("The Python programming language was created by Guido van Rossum.",
         "Meditation reduces stress and improves mental health."),
     "not_supported"),
    ("hall-nsp-09",
     _hp("Photosynthesis converts sunlight into energy in plants.",
         "The French Revolution began in seventeen eighty-nine."),
     "not_supported"),
    ("hall-nsp-10",
     _hp("The speed of light in a vacuum is approximately three hundred million "
         "meters per second.",
         "Jazz music originated in New Orleans during the early twentieth century."),
     "not_supported"),
    ("hall-nsp-11",
     _hp("Neil Armstrong was the first human to walk on the Moon.",
         "Blockchain technology enables secure decentralized transactions."),
     "not_supported"),
    ("hall-nsp-12",
     _hp("The human body has two hundred and six bones in adults.",
         "Solar panels convert sunlight into electrical energy."),
     "not_supported"),
    ("hall-nsp-13",
     _hp("Jupiter is the fifth planet from the Sun and the largest in the Solar System.",
         "Antibiotics kill or inhibit the growth of bacteria."),
     "not_supported"),
]
# fmt: on


def hallucination_suite() -> Suite:
    """Return the 25-task hallucination-detection benchmark suite."""
    tasks = [
        BenchmarkTask(task_id=tid, input=inp, expected_output=exp)
        for tid, inp, exp in _HALLUCINATION_TASKS
    ]
    return Suite(name="hallucination", tasks=tasks)


async def hallucination_agent(input_text: str) -> str:  # noqa: RUF029
    """Check whether the CLAIM in *input_text* is supported by the PASSAGE.

    Returns ``"supported"`` or ``"not_supported"``.
    Uses :class:`~llm_agents.evaluation.hallucination.OverlapDetector` with
    ``threshold=0.5``.
    """
    from llm_agents.evaluation.hallucination import OverlapDetector  # noqa: PLC0415

    parts = input_text.split("\nCLAIM: ", 1)
    if len(parts) != 2:
        return "not_supported"
    passage = parts[0].removeprefix("PASSAGE: ")
    claim = parts[1]
    detector = OverlapDetector(threshold=0.5, sentence_threshold=0.3)
    report = detector.detect(answer=claim, references=[passage])
    return "supported" if not report.is_hallucination else "not_supported"


# ---------------------------------------------------------------------------
# Suite 4: classification — 20 sentiment classification tasks
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: frozenset[str] = frozenset({
    "excellent", "love", "wonderful", "amazing", "fantastic", "brilliant",
    "best", "perfect", "great", "happy", "enjoy", "impressive", "outstanding",
    "superb", "delightful",
})

_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "terrible", "awful", "worst", "hate", "bad", "horrible", "disappointing",
    "poor", "useless", "dreadful", "disgusting", "appalling", "pathetic", "waste",
})

# fmt: off
_CLASSIFICATION_TASKS: list[tuple[str, str, str]] = [
    # (task_id, text, expected_label)

    # Positive (10)
    ("cls-pos-01", "This product is excellent and I absolutely love it.", "positive"),
    ("cls-pos-02", "Wonderful service and amazing quality, highly recommend.", "positive"),
    ("cls-pos-03", "The best experience ever, absolutely fantastic and brilliant.", "positive"),
    ("cls-pos-04", "Perfect quality and great value for money.", "positive"),
    ("cls-pos-05", "I am so happy with this purchase, it is outstanding.", "positive"),
    ("cls-pos-06", "Superb craftsmanship and delightful design.", "positive"),
    ("cls-pos-07", "An impressive and excellent product that I enjoy daily.", "positive"),
    ("cls-pos-08", "Great product with brilliant features and amazing performance.", "positive"),
    ("cls-pos-09", "I love this wonderful and perfect product.", "positive"),
    ("cls-pos-10", "The fantastic quality makes this the best product I have bought.", "positive"),

    # Negative (10)
    ("cls-neg-01", "This product is terrible and completely useless.", "negative"),
    ("cls-neg-02", "Awful quality and the worst purchase I have ever made.", "negative"),
    ("cls-neg-03", "I hate this product, it is horrible and pathetic.", "negative"),
    ("cls-neg-04", "Dreadful experience and poor quality overall.", "negative"),
    ("cls-neg-05", "Disappointing and bad, would not recommend to anyone.", "negative"),
    ("cls-neg-06", "This is appalling, an absolute waste of money.", "negative"),
    ("cls-neg-07", "Horrible and disgusting product, completely useless.", "negative"),
    ("cls-neg-08", "The worst quality I have seen, terrible craftsmanship.", "negative"),
    ("cls-neg-09", "Such a bad and disappointing experience overall.", "negative"),
    ("cls-neg-10", "Awful and pathetic, I hate this dreadful thing.", "negative"),
]
# fmt: on


def classification_suite() -> Suite:
    """Return the 20-task sentiment classification benchmark suite."""
    tasks = [
        BenchmarkTask(task_id=tid, input=text, expected_output=label)
        for tid, text, label in _CLASSIFICATION_TASKS
    ]
    return Suite(name="classification", tasks=tasks)


async def classification_agent(input_text: str) -> str:  # noqa: RUF029
    """Classify *input_text* as ``"positive"`` or ``"negative"`` by keyword count."""
    import re  # noqa: PLC0415

    words = set(re.findall(r"\w+", input_text.lower()))
    pos_count = len(words & _POSITIVE_WORDS)
    neg_count = len(words & _NEGATIVE_WORDS)
    return "positive" if pos_count >= neg_count else "negative"


# ---------------------------------------------------------------------------
# Built-in registries
# ---------------------------------------------------------------------------

BUILTIN_SUITES: dict[str, Suite] = {
    "tiny": _build_tiny_suite(),
    "arithmetic": arithmetic_suite(),
    "qa_lookup": qa_lookup_suite(),
    "hallucination": hallucination_suite(),
    "classification": classification_suite(),
}

BUILTIN_AGENTS: dict[str, AsyncAgent] = {
    "tiny": _tiny_agent,
    "arithmetic": arithmetic_agent,
    "qa_lookup": qa_lookup_agent,
    "hallucination": hallucination_agent,
    "classification": classification_agent,
}
