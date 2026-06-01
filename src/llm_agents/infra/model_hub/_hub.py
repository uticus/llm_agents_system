"""ModelHub: registry for named model backends with optional version tracking.

:class:`ModelHub` maps string names to :class:`ModelBackend`-compatible
objects.  Registering a name a second time overwrites the previous entry.

Versioning is opt-in: pass a *version_logger* to enable it.  Calling
:meth:`register_version` records the backend under an explicit version string
so earlier checkpoints can be retrieved or restored via :meth:`rollback`.

Without a *version_logger*, all versioning methods are fully usable; logging
side-effects are simply skipped.  Passing an :class:`MLflowVersionLogger`
instance enables MLflow run creation on every register and rollback event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llm_agents.infra.model_hub._backend import ModelBackend


class ModelHub:
    """Registry that maps backend names to :class:`ModelBackend` instances.

    Backends registered here can be retrieved by name for routing or
    direct invocation.

    Versioning is opt-in.  Use :meth:`register_version` instead of (or in
    addition to) :meth:`register` to track named checkpoints.  The active
    version — the one returned by :meth:`get` — can be rolled back to any
    earlier checkpoint with :meth:`rollback`.

    Args:
        backends: Optional initial mapping of ``name → backend``.
        version_logger: Optional logger called on :meth:`register_version` and
            :meth:`rollback` events.  Must expose ``on_register`` and
            ``on_rollback`` methods (see :class:`MLflowVersionLogger`).
    """

    def __init__(
        self,
        backends: dict[str, Any] | None = None,
        *,
        version_logger: Any | None = None,
    ) -> None:
        self._backends: dict[str, Any] = dict(backends or {})
        self._versions: dict[str, list[str]] = {}  # name -> insertion-ordered version list
        self._version_map: dict[str, dict[str, Any]] = {}  # name -> {version: backend}
        self._active_versions: dict[str, str] = {}  # name -> currently active version
        self._version_logger = version_logger

    # ------------------------------------------------------------------
    # Core registration / retrieval
    # ------------------------------------------------------------------

    def register(self, backend: ModelBackend) -> None:
        """Register *backend* under its :attr:`~ModelBackend.name`.

        Registering a second backend with the same name overwrites the first.

        Args:
            backend: A :class:`ModelBackend`-compatible object.
        """
        self._backends[backend.name] = backend

    def get(self, name: str) -> ModelBackend | None:
        """Return the backend registered under *name*, or ``None``.

        When version tracking is active for *name*, this always returns the
        *active* version (i.e. the most recently registered or the version
        last set by :meth:`rollback`).
        """
        return self._backends.get(name)

    def list_names(self) -> list[str]:
        """Return all registered backend names (alphabetical order)."""
        return sorted(self._backends)

    def __len__(self) -> int:
        return len(self._backends)

    # ------------------------------------------------------------------
    # Version tracking
    # ------------------------------------------------------------------

    def register_version(
        self,
        backend: ModelBackend,
        version: str,
        *,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Register *backend* under its name **and** a specific *version* tag.

        - The backend is stored in both the flat ``_backends`` registry and the
          per-name version history.
        - The registered *version* becomes the *active* version: :meth:`get`
          will return this backend until a subsequent :meth:`register_version`
          or :meth:`rollback` changes it.
        - Registering the same *version* string again overwrites the previous
          checkpoint for that version.
        - If a *version_logger* was supplied at construction time, its
          ``on_register(name, version, metadata, tags)`` method is called.

        Args:
            backend: A :class:`ModelBackend`-compatible object.
            version: Opaque version identifier (e.g. ``"v1"``, ``"2024-06-01"``).
            tags:    Optional key/value metadata to attach to the log event.
        """
        name = backend.name
        if name not in self._versions:
            self._versions[name] = []
            self._version_map[name] = {}

        if version not in self._version_map[name]:
            self._versions[name].append(version)

        self._version_map[name][version] = backend
        self._active_versions[name] = version
        self._backends[name] = backend

        if self._version_logger is not None:
            self._version_logger.on_register(
                name,
                version,
                backend.metadata(),
                tags or {},
            )

    def get_version(self, name: str, version: str) -> ModelBackend | None:
        """Return the backend stored under *name* at *version*, or ``None``.

        Unlike :meth:`get`, this always retrieves the exact checkpoint — it
        does **not** alter the active version.

        Args:
            name:    Backend name.
            version: Version identifier previously passed to
                     :meth:`register_version`.
        """
        return self._version_map.get(name, {}).get(version)

    def list_versions(self, name: str) -> list[str]:
        """Return the list of known versions for *name* in registration order.

        Returns an empty list if no versions have been registered for *name*.

        Args:
            name: Backend name.
        """
        return list(self._versions.get(name, []))

    def active_version(self, name: str) -> str | None:
        """Return the currently active version string for *name*, or ``None``.

        ``None`` means *name* was registered without version tracking, or has
        not been registered at all.

        Args:
            name: Backend name.
        """
        return self._active_versions.get(name)

    def rollback(self, name: str, version: str) -> bool:
        """Set the active backend for *name* to an earlier *version*.

        - :meth:`get` will return the checkpoint backend after this call.
        - The rollback event is forwarded to the *version_logger* (if any).

        Args:
            name:    Backend name.
            version: Version to restore; must have been registered previously
                     via :meth:`register_version`.

        Returns:
            ``True`` if the rollback succeeded, ``False`` if *name* or
            *version* is unknown.
        """
        if name not in self._version_map or version not in self._version_map[name]:
            return False

        previous = self._active_versions.get(name)
        self._active_versions[name] = version
        self._backends[name] = self._version_map[name][version]

        if self._version_logger is not None:
            self._version_logger.on_rollback(name, previous, version)

        return True
