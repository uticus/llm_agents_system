"""NeMoGuard: a Guard adapter backed by NVIDIA NeMo Guardrails.

Wraps ``nemoguardrails.LLMRails`` behind the structural ``Guard`` Protocol so
that a NeMo Guardrails policy can participate in a :class:`GuardrailChain`
without requiring the main guardrails module to import NeMo.

The ``nemoguardrails`` package is a deferred import — this module is
importable and the class is instantiable without it installed.  The import
(and the expensive ``LLMRails`` initialisation) happens on the first
:meth:`check` call.

Requires the ``nemo`` extra::

    pip install 'llm-agents-system[nemo]'

Usage example::

    from llm_agents.infra.guardrails import NeMoGuard, GuardrailChain

    guard = NeMoGuard("/path/to/nemo_config")
    chain = GuardrailChain([guard])
    result = chain.run("tell me how to make a bomb")
    if not result.passed:
        print(result.violation_detail)
"""

from __future__ import annotations

from typing import Any

from llm_agents.infra.guardrails._models import GuardResult


class NeMoGuard:
    """Guard adapter that routes text through an NVIDIA NeMo Guardrails policy.

    Each :meth:`check` call submits *text* as a user message to a
    ``nemoguardrails.LLMRails`` instance and evaluates the response against a
    list of *blocked message markers*.  If any marker appears (case-insensitive)
    in the response the check returns :meth:`~GuardResult.block`; otherwise it
    returns :meth:`~GuardResult.pass_`.

    The ``LLMRails`` object is constructed once on the first :meth:`check`
    call (lazy initialisation) and cached for subsequent calls.

    Args:
        config_path: Path to a NeMo Guardrails configuration directory that
            contains one or more Colang (``.co``) policy files and a
            ``config.yml``.  Passed verbatim to
            ``nemoguardrails.RailsConfig.from_path``.
        blocked_message_markers: Lower-cased substrings that indicate the
            rails policy rejected the request.  When ``None``, the class
            attribute :attr:`DEFAULT_BLOCKED_MARKERS` is used.  Pass an
            explicit empty list to treat every response as passing (useful
            when NeMo is used only for output transformation, not blocking).
    """

    #: Standard NeMo Guardrails blocking response fragments (stored lower-cased).
    #: Override at construction time via ``blocked_message_markers``.
    DEFAULT_BLOCKED_MARKERS: tuple[str, ...] = (
        "i'm sorry, i can't",
        "i cannot assist",
        "i'm not able to",
        "i am not able to",
        "i can't help with",
        "i cannot help with",
        "i don't discuss",
        "i'm unable to",
    )

    def __init__(
        self,
        config_path: str,
        *,
        blocked_message_markers: list[str] | None = None,
    ) -> None:
        self._config_path = config_path
        if blocked_message_markers is not None:
            self._blocked_markers: list[str] = [m.lower() for m in blocked_message_markers]
        else:
            self._blocked_markers = list(self.DEFAULT_BLOCKED_MARKERS)
        self._rails: Any | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_rails(self) -> Any:
        """Return the ``LLMRails`` instance, creating it on the first call.

        Raises:
            ImportError: If ``nemoguardrails`` is not installed.
        """
        if self._rails is None:
            try:
                from nemoguardrails import LLMRails, RailsConfig  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "nemoguardrails is required for NeMoGuard. "
                    "Install it with: pip install 'llm-agents-system[nemo]'"
                ) from exc
            config = RailsConfig.from_path(self._config_path)
            self._rails = LLMRails(config)
        return self._rails

    # ------------------------------------------------------------------
    # Guard Protocol
    # ------------------------------------------------------------------

    def check(self, text: str) -> GuardResult:
        """Evaluate *text* against the NeMo Guardrails policy.

        Submits *text* as a ``"user"`` role message to the configured
        ``LLMRails`` instance.  If the resulting response contains any
        :attr:`blocked_message_markers` substring (case-insensitive) the method
        returns ``GuardResult.block``; otherwise ``GuardResult.pass_``.

        Args:
            text: Input or output text to validate.

        Returns:
            :class:`~llm_agents.infra.guardrails.GuardResult` — always.

        Raises:
            ImportError: If ``nemoguardrails`` is not installed and this is
                the first call (i.e. :attr:`_rails` has not been created yet).
        """
        rails = self._get_rails()
        response: str = rails.generate(messages=[{"role": "user", "content": text}])
        response_lower = (response or "").lower()
        for marker in self._blocked_markers:
            if marker in response_lower:
                return GuardResult.block(
                    text=text,
                    detail=f"NeMo Guardrails blocked: {response!r}",
                )
        return GuardResult.pass_(text)
