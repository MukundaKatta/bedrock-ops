"""Throttle code normalization tests."""

from __future__ import annotations

import pytest

from bedrock_ops._retry import (
    _normalize_after_call,
    install_throttle_normalizer,
    production_retry_config,
)


@pytest.mark.parametrize(
    "input_code,expected_code",
    [
        ("throttlingException", "ThrottlingException"),
        ("Throttled", "ThrottlingException"),
        ("tooManyRequestsException", "ThrottlingException"),
        ("ProvisionedThroughputExceededException", "ThrottlingException"),
        ("THROTTLING", "ThrottlingException"),
        ("ThrottlingException", "ThrottlingException"),
    ],
)
def test_throttle_codes_get_normalized(input_code: str, expected_code: str) -> None:
    parsed = {"Error": {"Code": input_code, "Message": "rate limited"}}
    _normalize_after_call(parsed)
    assert parsed["Error"]["Code"] == expected_code


def test_non_throttle_codes_pass_through() -> None:
    parsed = {"Error": {"Code": "ValidationException", "Message": "bad input"}}
    _normalize_after_call(parsed)
    assert parsed["Error"]["Code"] == "ValidationException"


def test_missing_error_key_is_safe() -> None:
    parsed: dict = {}
    _normalize_after_call(parsed)
    assert parsed == {}


def test_non_dict_input_is_safe() -> None:
    _normalize_after_call(None)  # type: ignore[arg-type]


def test_install_throttle_normalizer_registers_hooks() -> None:
    class _FakeEvents:
        def __init__(self) -> None:
            self.registrations: list[tuple[str, object]] = []

        def register(self, event: str, handler: object) -> None:
            self.registrations.append((event, handler))

    class _FakeMeta:
        events = _FakeEvents()

    class _FakeClient:
        meta = _FakeMeta()

    install_throttle_normalizer(_FakeClient())
    events = [r[0] for r in _FakeClient.meta.events.registrations]
    assert "after-call.bedrock-runtime" in events
    assert "after-call.bedrock-agent-runtime" in events


def test_production_retry_config_has_adaptive_mode_and_long_read_timeout() -> None:
    cfg = production_retry_config()
    assert cfg.retries["mode"] == "adaptive"
    assert cfg.retries["max_attempts"] == 5
    assert cfg.connect_timeout == 10.0
    assert cfg.read_timeout == 120.0
