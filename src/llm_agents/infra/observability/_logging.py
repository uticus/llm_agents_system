"""Structured JSON logger for the observability subsystem.

Wraps stdlib ``logging`` with a ``JSONFormatter`` that produces one JSON object
per log line.  Each record includes the active trace/span ids from
``infra/tracing.current_span()`` so that log lines and spans can be correlated
without any external log shipper.

Usage::

    from llm_agents.infra.observability import get_logger

    log = get_logger(__name__)
    log.info("model called", model="gpt-4o", tokens=256)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format a ``LogRecord`` as a single-line JSON object.

    Fields always present:
        timestamp  ISO-8601 UTC string derived from ``record.created``.
        level      Uppercase level name (e.g. ``"INFO"``).
        logger     Logger name (``record.name``).
        message    Rendered log message (``record.getMessage()``).
        trace_id   Active span trace id, or ``null``.
        span_id    Active span id, or ``null``.

    Extra fields from the caller's ``**kwargs`` are merged in from
    ``record._extra`` (set by :class:`StructuredLogger._log`).
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Deferred import avoids circular dependency if tracing ever imports
        # observability at module level.
        from llm_agents.infra.tracing import current_span  # noqa: PLC0415

        span = current_span()
        data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": span.trace_id if span is not None else None,
            "span_id": span.span_id if span is not None else None,
        }
        extra = getattr(record, "_extra", {})
        if extra:
            data.update(extra)
        return json.dumps(data)


class StructuredLogger:
    """Thin wrapper around a stdlib :class:`logging.Logger`.

    Each ``debug``/``info``/``warning``/``error``/``critical`` call passes
    keyword arguments as extra JSON fields via the underlying ``_extra``
    mechanism consumed by :class:`JSONFormatter`.

    A ``StreamHandler`` to *stdout* with :class:`JSONFormatter` is added once
    when no handlers are configured on this logger or the root logger.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        # Add handler only when there is no handler anywhere in the hierarchy.
        if not self._logger.handlers and not logging.root.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    def _log(self, level: int, msg: str, **extra: Any) -> None:
        self._logger.log(level, msg, extra={"_extra": extra})

    def debug(self, msg: str, **extra: Any) -> None:
        """Log *msg* at DEBUG level with optional extra JSON fields."""
        self._log(logging.DEBUG, msg, **extra)

    def info(self, msg: str, **extra: Any) -> None:
        """Log *msg* at INFO level with optional extra JSON fields."""
        self._log(logging.INFO, msg, **extra)

    def warning(self, msg: str, **extra: Any) -> None:
        """Log *msg* at WARNING level with optional extra JSON fields."""
        self._log(logging.WARNING, msg, **extra)

    def error(self, msg: str, **extra: Any) -> None:
        """Log *msg* at ERROR level with optional extra JSON fields."""
        self._log(logging.ERROR, msg, **extra)

    def critical(self, msg: str, **extra: Any) -> None:
        """Log *msg* at CRITICAL level with optional extra JSON fields."""
        self._log(logging.CRITICAL, msg, **extra)


# Module-level cache — one StructuredLogger per name.
_logger_cache: dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    """Return the cached :class:`StructuredLogger` for *name*, creating it if needed."""
    if name not in _logger_cache:
        _logger_cache[name] = StructuredLogger(name)
    return _logger_cache[name]
