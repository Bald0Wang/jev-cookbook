"""Standard-library logging with credential redaction.

The SDK emits to the ``typesafe_sdk`` logger and never configures handlers or levels beyond an
optional convenience: set ``TYPESAFE_LOG_LEVEL`` (``debug``/``info``/...) and the level is applied
once at import. Otherwise configure the ``typesafe_sdk`` logger through standard logging as usual.
"""

import logging
import os

from typing_extensions import override

from typesafe_sdk._core.constants import LOGGER_NAME, SECRET_HEADERS
from typesafe_sdk.constants import LOG_LEVEL_ENV

logger = logging.getLogger(LOGGER_NAME)


LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "off": logging.CRITICAL + 1,
}


def _is_secret(name: str) -> bool:
    lowered = name.lower()
    return lowered in SECRET_HEADERS or "token" in lowered or "secret" in lowered


def _redact(headers: dict[str, str]) -> dict[str, str]:
    return {name: "***" if _is_secret(name) else value for name, value in headers.items()}


class SensitiveHeadersFilter(logging.Filter):
    """Redact credential-bearing headers from a record before it reaches any handler.

    Log calls pass headers as the ``headers`` key of a mapping-style ``args``; this filter is the
    single redaction point, so no call site can leak a secret header.
    """

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, dict):
            headers = args.get("headers")
            if isinstance(headers, dict):
                record.args = {**args, "headers": _redact(headers)}
        return True


def setup_logging() -> None:
    """Apply ``TYPESAFE_LOG_LEVEL`` to the ``typesafe_sdk`` logger if it names a known level."""
    level = (os.environ.get(LOG_LEVEL_ENV) or "").strip().lower()
    if level in LOG_LEVELS:
        logger.setLevel(LOG_LEVELS[level])


logger.addHandler(logging.NullHandler())
logger.addFilter(SensitiveHeadersFilter())
setup_logging()
