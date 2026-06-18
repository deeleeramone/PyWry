"""Tests for pywry.log."""

from __future__ import annotations

import logging

import pytest

from pywry.log import (
    _LoggerHolder,
    debug,
    enable_debug,
    error,
    exception,
    get_logger,
    info,
    log_callback_error,
    redact_sensitive_data,
    set_level,
    warn,
)


@pytest.fixture(autouse=True)
def _reset_logger_holder():
    """Reset the logger holder so each test starts from a known state."""
    saved = _LoggerHolder.instance
    _LoggerHolder.instance = None
    # Clear handlers from any existing pywry logger
    pywry_logger = logging.getLogger("pywry")
    saved_handlers = list(pywry_logger.handlers)
    pywry_logger.handlers.clear()
    saved_level = pywry_logger.level
    yield
    pywry_logger.handlers.clear()
    pywry_logger.handlers.extend(saved_handlers)
    pywry_logger.setLevel(saved_level)
    _LoggerHolder.instance = saved


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "pywry"

    def test_singleton(self):
        a = get_logger()
        b = get_logger()
        assert a is b

    def test_attaches_handler_when_missing(self):
        logger = get_logger()
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_does_not_duplicate_handler(self):
        logger = logging.getLogger("pywry")
        existing = logging.StreamHandler()
        logger.addHandler(existing)
        # Reset _LoggerHolder so get_logger reinitializes
        _LoggerHolder.instance = None
        new_logger = get_logger()
        # No new handler added because one already exists
        handlers_count_after_first = len(new_logger.handlers)
        # Calling again shouldn't add more
        get_logger()
        assert len(new_logger.handlers) == handlers_count_after_first


class TestLogFunctions:
    def test_debug_does_not_raise(self):
        debug("debug msg")

    def test_info_does_not_raise(self):
        info("info msg")

    def test_warn_does_not_raise(self):
        warn("warn msg")

    def test_error_does_not_raise(self):
        error("error msg")

    def test_exception_does_not_raise(self):
        try:
            raise ValueError("x")
        except ValueError:
            exception("oops")

    def test_log_callback_error(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            log_callback_error("evt:x", "main", e)


class TestSetLevel:
    def test_int_level(self):
        set_level(logging.DEBUG)
        assert get_logger().level == logging.DEBUG

    def test_string_level(self):
        set_level("DEBUG")
        assert get_logger().level == logging.DEBUG

    def test_string_level_lower_case(self):
        set_level("info")
        assert get_logger().level == logging.INFO


class TestEnableDebug:
    def test_sets_debug_level(self):
        enable_debug()
        assert get_logger().level == logging.DEBUG


class TestRedactSensitiveData:
    def test_none_passthrough(self):
        assert redact_sensitive_data(None) is None

    def test_string_passthrough(self):
        assert redact_sensitive_data("hello") == "hello"

    def test_dict_redacts_sensitive_keys(self):
        data = {"name": "Alice", "password": "s3cret", "token": "abc"}
        result = redact_sensitive_data(data)
        assert result["name"] == "Alice"
        assert result["password"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"

    def test_dict_partial_match(self):
        data = {"my_api_key": "x", "userKey": "y"}
        result = redact_sensitive_data(data)
        # Both contain sensitive substrings
        assert result["my_api_key"] == "[REDACTED]"
        assert result["userKey"] == "[REDACTED]"

    def test_nested_dict_redaction(self):
        data = {"user": {"name": "x", "secret": "y"}}
        result = redact_sensitive_data(data)
        assert result["user"]["secret"] == "[REDACTED]"
        assert result["user"]["name"] == "x"

    def test_list_redaction(self):
        data = [{"password": "x"}, {"name": "y"}]
        result = redact_sensitive_data(data)
        assert result[0]["password"] == "[REDACTED]"
        assert result[1]["name"] == "y"

    def test_max_depth(self):
        data = {"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}}
        # max_depth=2 -> at depth 2 the recursion returns "[MAX_DEPTH]"
        result = redact_sensitive_data(data, max_depth=2)
        assert result == {"a": {"b": "[MAX_DEPTH]"}} or "[MAX_DEPTH]" in str(result)

    def test_max_depth_zero(self):
        result = redact_sensitive_data({"k": "v"}, max_depth=0)
        assert result == "[MAX_DEPTH]"

    def test_non_string_key(self):
        data = {1: "value", 2: "another"}
        result = redact_sensitive_data(data)
        assert result == {1: "value", 2: "another"}
