"""Logging helpers for the Case Monitor scripts."""
from __future__ import annotations

import logging
import os
from typing import Optional

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _parse_level(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return getattr(logging, value.upper(), logging.INFO)


def setup_logging(level: Optional[str] = None) -> None:
    """Configure application logging once."""
    if logging.getLogger().handlers:
        return

    env_level = level or os.getenv("CASE_MONITOR_LOG_LEVEL", "INFO")
    logging.basicConfig(level=_parse_level(env_level), format=_LOG_FORMAT)
