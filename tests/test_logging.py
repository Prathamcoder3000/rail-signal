"""
Unit tests for centralized logging configuration and secret sanitization
in backend/app/logging_config.py.
"""

import logging
from backend.app.logging_config import (
    SanitizingLogFormatter,
    configure_logging,
    sanitize_log_message,
)


def test_sanitize_log_message_credentials():
    """Verifies that sensitive passwords, tokens, and DB URIs are masked."""
    assert sanitize_log_message("Connecting with password=secret123 to DB") == "Connecting with password=*** to DB"
    assert sanitize_log_message("Using pwd=my_pass;") == "Using pwd=***;"
    assert sanitize_log_message("URI postgres://postgres:secure_pw@localhost:5432/rail_signal") == "URI postgres://postgres:***@localhost:5432/rail_signal"
    assert sanitize_log_message("URI postgresql://admin:pass_word@db.host:5432/prod") == "URI postgresql://admin:***@db.host:5432/prod"
    assert sanitize_log_message("Auth Bearer eyJhbGciOiJIUzI1NiIs.token_data") == "Auth Bearer ***"
    assert sanitize_log_message("API token=xyz987abc;") == "API token=***;"


def test_sanitize_log_message_preserves_normal_text():
    """Verifies that non-sensitive strings are preserved without alteration."""
    normal = "Processed 5,207 trains across 8,988 stations in 1.45 seconds."
    assert sanitize_log_message(normal) == normal


def test_sanitizing_formatter_formats_and_scrubs():
    """Verifies that SanitizingLogFormatter scrubs records emitted via standard logging."""
    formatter = SanitizingLogFormatter("%(levelname)s: %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting using password=super_secret_pw to db",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "super_secret_pw" not in formatted
    assert "password=***" in formatted


def test_configure_logging_idempotent():
    """Verifies that calling configure_logging multiple times does not duplicate stream handlers."""
    logger1 = configure_logging(force_reconfigure=True)
    initial_handler_count = len(logger1.handlers)
    assert initial_handler_count == 1

    # Call again
    logger2 = configure_logging()
    assert len(logger2.handlers) == initial_handler_count
    assert logger1 is logger2


def test_configure_logging_quiet_mode():
    """Verifies that quiet=True elevates threshold to WARNING."""
    logger = configure_logging(quiet=True, force_reconfigure=True)
    assert logger.level == logging.WARNING

    # Reset back to INFO
    logger_normal = configure_logging(quiet=False, force_reconfigure=True)
    assert logger_normal.level == logging.INFO


def test_child_loggers_propagate_and_have_no_duplicate_handlers():
    """Verifies that child loggers propagate to root and do not accumulate duplicate handlers."""
    configure_logging(force_reconfigure=True)
    sub = logging.getLogger("rail_signal.transformation")
    assert sub.propagate is True
    assert len(sub.handlers) == 0
