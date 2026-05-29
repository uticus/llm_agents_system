"""ModelHub: registry for named model backends.

:class:`ModelHub` maps string names to :class:`ModelBackend`-compatible
objects.  Registering a name a second time overwrites the previous entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_agents.infra.model_hub._backend import ModelBackend


class ModelHub:
    """Registry that maps backend names to :class:`ModelBackend` instances.

    Backends registered here can be retrieved by name for routing or
    direct invocation.

    Args:
        backends: Optional initial mapping of ``name → backend``.
    """

    def __init__(self, backends: dict[str, Any] | None = None) -> None:
        self._backends: dict[str, Any] = dict(backends or {})

    def register(self, backend: ModelBackend) -> None:
        """Register *backend* under its :attr:`~ModelBackend.name`.

        Registering a second backend with the same name overwrites the first.

        Args:
            backend: A :class:`ModelBackend`-compatible object.
        """
        self._backends[backend.name] = backend

    def get(self, name: str) -> ModelBackend | None:
        """Return the backend registered under *name*, or ``None``."""
        return self._backends.get(name)

    def list_names(self) -> list[str]:
        """Return all registered backend names (alphabetical order)."""
        return sorted(self._backends)

    def __len__(self) -> int:
        return len(self._backends)
