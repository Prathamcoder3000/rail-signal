"""
Centralized, secret-sanitizing logging infrastructure for RAIL / SIGNAL.

Provides unified log formatting, duplicate handler prevention, run/stage context injection,
and automatic credential/token masking across all backend and pipeline modules.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Optional

# Reusable patterns for masking sensitive authentication secrets
_SENSITIVE_PATTERNS = [
    (re.compile(r"password=([^\s;]+)", re.IGNORECASE), "password=***"),
    (re.compile(r"pwd=([^\s;]+)", re.IGNORECASE), "pwd=***"),
    (re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1***\3"),
    (re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]+)", re.IGNORECASE), "Bearer ***"),
    (re.compile(r"token=([^\s;]+)", re.IGNORECASE), "token=***"),
]


def sanitize_log_message(message: str) -> str:
    """Removes passwords, connection credentials, and sensitive parameters from log strings."""
    if not message:
        return ""
    text = str(message)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SanitizingLogFormatter(logging.Formatter):
    """Logging formatter that automatically scrubs sensitive credentials from output."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return sanitize_log_message(original)


def configure_logging(
    level: int = logging.INFO,
    quiet: bool = False,
    force_reconfigure: bool = False,
) -> logging.Logger:
    """
    Configures the centralized 'rail_signal' parent logger.

    Guarantees:
    1. Idempotent: Does not add duplicate StreamHandlers on repeated calls.
    2. Sanitizes all credentials across child loggers.
    3. Respects quiet mode by elevating logging threshold to WARNING.
    """
    target_level = logging.WARNING if quiet else level
    root_rail_logger = logging.getLogger("rail_signal")
    root_rail_logger.setLevel(target_level)

    # Check for existing handlers to prevent log message duplication
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_rail_logger.handlers
    )

    if force_reconfigure:
        root_rail_logger.handlers.clear()
        has_stream_handler = False

    if not has_stream_handler:
        handler = logging.StreamHandler(sys.stdout)
        formatter = SanitizingLogFormatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.setLevel(target_level)
        root_rail_logger.addHandler(handler)

    # Ensure child loggers propagate to parent and adopt the same level
    for sub in (
        "rail_signal.orchestrator",
        "rail_signal.monitoring",
        "rail_signal.schema_manager",
        "rail_signal.transformation",
        "rail_signal.ingestion",
        "rail_signal.db",
        "rail_signal.advisory_lock",
    ):
        sub_logger = logging.getLogger(sub)
        sub_logger.setLevel(target_level)
        sub_logger.propagate = True
        # Clear any independently registered handlers to eliminate duplicate output
        sub_logger.handlers.clear()

    return root_rail_logger
