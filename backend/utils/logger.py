"""
Structured logging helper.

Emits JSON-formatted log lines when ``python-json-logger`` is installed
(added to requirements.txt). Falls back to plain text if the package is
absent so local development is unaffected.

``LOG_LEVEL`` environment variable controls the minimum level:
    LOG_LEVEL=DEBUG | INFO | WARNING | ERROR | CRITICAL  (default: INFO)
"""
import logging
import os
import sys

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with structured JSON formatting."""
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    level = getattr(logging, _LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    try:
        from pythonjsonlogger import jsonlogger  # type: ignore

        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    except ImportError:
        # Fallback: plain text — acceptable for local dev.
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Prevent log records from bubbling to the root logger and doubling.
    logger.propagate = False
    return logger
