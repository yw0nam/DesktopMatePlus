"""Tests for core-level ErrorClassifier."""

from src.core.error_classifier import ErrorClassifier, ErrorSeverity


class TestErrorSeverity:
    def test_values_are_strings(self):
        assert ErrorSeverity.TRANSIENT == "transient"
        assert ErrorSeverity.RECOVERABLE == "recoverable"
        assert ErrorSeverity.FATAL == "fatal"


class TestErrorClassifierClassify:
    def test_timeout_is_transient(self):
        assert ErrorClassifier.classify(TimeoutError()) == ErrorSeverity.TRANSIENT

    def test_connection_reset_is_transient(self):
        assert (
            ErrorClassifier.classify(ConnectionResetError()) == ErrorSeverity.TRANSIENT
        )

    def test_broken_pipe_is_transient(self):
        assert ErrorClassifier.classify(BrokenPipeError()) == ErrorSeverity.TRANSIENT

    def test_value_error_is_recoverable(self):
        assert ErrorClassifier.classify(ValueError("bad")) == ErrorSeverity.RECOVERABLE

    def test_key_error_is_recoverable(self):
        assert ErrorClassifier.classify(KeyError("k")) == ErrorSeverity.RECOVERABLE

    def test_runtime_error_is_fatal(self):
        assert ErrorClassifier.classify(RuntimeError("boom")) == ErrorSeverity.FATAL

    def test_unknown_exception_defaults_to_fatal(self):
        class _Custom(Exception):
            pass

        assert ErrorClassifier.classify(_Custom()) == ErrorSeverity.FATAL

    def test_subclass_inherits_severity(self):
        class _Sub(ValueError):
            pass

        assert ErrorClassifier.classify(_Sub("x")) == ErrorSeverity.RECOVERABLE


class TestErrorClassifierShouldRetry:
    def test_fatal_never_retries(self):
        assert not ErrorClassifier.should_retry(RuntimeError(), 0, 10)

    def test_transient_retries_within_tolerance(self):
        assert ErrorClassifier.should_retry(TimeoutError(), 1, 3)

    def test_exceeds_tolerance_no_retry(self):
        assert not ErrorClassifier.should_retry(TimeoutError(), 5, 3)

    def test_recoverable_retries_within_tolerance(self):
        assert ErrorClassifier.should_retry(ValueError("x"), 0, 3)


class TestErrorClassifierBackoffDelay:
    def test_transient_no_delay(self):
        assert ErrorClassifier.get_backoff_delay(TimeoutError(), 1.0) == 0.0

    def test_recoverable_uses_base_delay(self):
        assert ErrorClassifier.get_backoff_delay(ValueError("x"), 2.0) == 2.0

    def test_fatal_no_delay(self):
        assert ErrorClassifier.get_backoff_delay(RuntimeError(), 1.0) == 0.0


class TestErrorClassifierServiceErrors:
    """ErrorClassifier with service-init-style exceptions."""

    def test_file_not_found_defaults_fatal(self):
        assert ErrorClassifier.classify(FileNotFoundError("cfg")) == ErrorSeverity.FATAL

    def test_os_error_defaults_fatal(self):
        assert ErrorClassifier.classify(OSError("io")) == ErrorSeverity.FATAL
