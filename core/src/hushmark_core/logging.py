"""Structured event logging whose schema cannot carry traffic bodies."""

from __future__ import annotations

import logging
from typing import Literal, TypedDict

import structlog


class CoreLogEvent(TypedDict, total=False):
    event: Literal["request_complete", "service_started"]
    route: str
    method: str
    status: int
    duration_ms: float


def configure_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", level=level.upper(), force=True)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def log_event(event: CoreLogEvent) -> None:
    structlog.get_logger("hushmark_core").info(**event)
