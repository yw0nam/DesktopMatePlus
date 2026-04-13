"""Tests for classify_health_severity module-level function in health.py."""

from src.core.error_classifier import ErrorSeverity
from src.services.health import classify_health_severity


def test_severity_none_returns_none() -> None:
    assert classify_health_severity(None) is None


def test_severity_connection_timeout_returns_transient() -> None:
    assert classify_health_severity("connection timeout") == ErrorSeverity.TRANSIENT


def test_severity_not_initialized_returns_recoverable() -> None:
    assert classify_health_severity("not initialized") == ErrorSeverity.RECOVERABLE


def test_severity_empty_string_returns_recoverable() -> None:
    assert classify_health_severity("") == ErrorSeverity.RECOVERABLE


def test_severity_whitespace_only_returns_recoverable() -> None:
    assert classify_health_severity("   ") == ErrorSeverity.RECOVERABLE


def test_severity_unknown_error_returns_fatal() -> None:
    assert classify_health_severity("unknown error xyz") == ErrorSeverity.FATAL
