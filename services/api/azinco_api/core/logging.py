"""Structured JSON logging with sensitive-value masking (BS §7.7, §12)."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

MASK = "***"
SENSITIVE_KEY = re.compile(
    r"pass(word)?|secret|token|authorization|api[_-]?key|cookie|session|credential|dsn",
    re.IGNORECASE,
)


def mask_value(value: Any) -> Any:
    """Recursively replace values of sensitive keys with '***' (used by logs and audit)."""
    if isinstance(value, Mapping):
        return {
            k: (MASK if isinstance(k, str) and SENSITIVE_KEY.search(k) else mask_value(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(mask_value(v) for v in value)
    return value


def mask_sensitive(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor: replace values of sensitive keys (at any depth) with '***'."""
    for key in list(event_dict):
        if SENSITIVE_KEY.search(key):
            event_dict[key] = MASK
        else:
            event_dict[key] = mask_value(event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            mask_sensitive,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(name)
    return logger
