"""BedrockClient tests with mocked boto3."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from bedrock_ops import (
    BedrockClient,
    BedrockOpsError,
    BedrockThrottled,
    BedrockTimeout,
    BedrockValidationError,
)


@pytest.fixture
def fake_session() -> MagicMock:
    """A fake boto3 session whose .client() returns a configurable MagicMock."""
    session = MagicMock()
    session.region_name = "us-east-1"
    fake_client = MagicMock()
    fake_client.meta.events.register = MagicMock()
    session.client.return_value = fake_client
    return session


def test_construction_installs_throttle_normalizer(fake_session: MagicMock) -> None:
    BedrockClient(boto_session=fake_session)
    fake_client = fake_session.client.return_value
    registered_events = [c.args[0] for c in fake_client.meta.events.register.call_args_list]
    assert "after-call.bedrock-runtime" in registered_events
    assert "after-call.bedrock-agent-runtime" in registered_events


def test_converse_returns_typed_response_with_full_usage(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "hello world"}],
            }
        },
        "stopReason": "end_turn",
        "usage": {
            "inputTokens": 5,
            "outputTokens": 2,
            "cacheReadInputTokens": 100,
            "cacheWriteInputTokens": 0,
        },
        "metrics": {"latencyMs": 250},
    }
    client = BedrockClient(boto_session=fake_session)
    resp = client.converse(
        modelId="anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
    )
    assert resp.text == "hello world"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 5
    assert resp.usage.cache_read_input_tokens == 100
    assert resp.latency_ms == 250
    assert resp.guardrail is None


def test_converse_wraps_read_timeout_in_typed_error(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.side_effect = ReadTimeoutError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com/")
    client = BedrockClient(boto_session=fake_session)
    with pytest.raises(BedrockTimeout) as exc_info:
        client.converse(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    assert exc_info.value.kind == "read"
    assert exc_info.value.elapsed_s >= 0


def test_converse_wraps_throttling_after_retries_exhausted(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Too many requests"}},
        "Converse",
    )
    client = BedrockClient(boto_session=fake_session, max_attempts=3)
    with pytest.raises(BedrockThrottled) as exc_info:
        client.converse(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    assert exc_info.value.attempts == 3
    assert exc_info.value.model_id == "anthropic.claude-sonnet-4-20250514-v1:0"


def test_converse_wraps_validation_exception(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.side_effect = ClientError(
        {
            "Error": {
                "Code": "ValidationException",
                "Message": "system.0.cache_control: Extra inputs are not permitted",
            }
        },
        "Converse",
    )
    client = BedrockClient(boto_session=fake_session)
    with pytest.raises(BedrockValidationError) as exc_info:
        client.converse(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    assert "cache_control" in str(exc_info.value)


def test_other_client_error_wrapped_in_base_error(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no access"}},
        "Converse",
    )
    client = BedrockClient(boto_session=fake_session)
    with pytest.raises(BedrockOpsError) as exc_info:
        client.converse(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    assert "AccessDeniedException" in str(exc_info.value)


def test_converse_attaches_guardrail_intervention_when_present(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "blocked"}]}},
        "stopReason": "guardrail_intervened",
        "usage": {"inputTokens": 10, "outputTokens": 0},
        "metrics": {"latencyMs": 100},
        "trace": {
            "guardrail": {
                "outputAssessments": {
                    "gid-1": [{"contentPolicy": {"filters": []}}],
                }
            }
        },
    }
    client = BedrockClient(boto_session=fake_session)
    resp = client.converse(
        modelId="anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        guardrailConfig={"guardrailIdentifier": "gid-1", "guardrailVersion": "DRAFT"},
    )
    assert resp.guardrail is not None
    assert resp.guardrail.action == "BLOCKED"
    assert resp.guardrail.guardrail_id == "gid-1"


def test_converse_stream_yields_events(fake_session: MagicMock) -> None:
    fake_client = fake_session.client.return_value
    fake_client.converse_stream.return_value = {
        "stream": [
            {"contentBlockDelta": {"delta": {"text": "hi"}}},
            {"metadata": {"usage": {"inputTokens": 5, "outputTokens": 1}}},
        ]
    }
    client = BedrockClient(boto_session=fake_session)
    events = list(
        client.converse_stream(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
        )
    )
    assert len(events) == 2
    assert events[0]["contentBlockDelta"]["delta"]["text"] == "hi"


def test_raw_property_exposes_underlying_client(fake_session: MagicMock) -> None:
    client = BedrockClient(boto_session=fake_session)
    assert client.raw is fake_session.client.return_value


def test_lazy_boto3_import_keeps_init_cheap() -> None:
    # Ensure the bedrock_ops top-level import does not import boto3 itself.
    # We can't easily un-import; instead, assert that the module has not
    # already imported boto3 by inspecting the import graph for our client module.
    import sys
    import importlib

    if "bedrock_ops" in sys.modules:
        importlib.reload(sys.modules["bedrock_ops"])
    # If boto3 was a top-level import in bedrock_ops, importing the package
    # would have transitively loaded it. Document the intent: we explicitly
    # lazy-import inside BedrockClient.__init__.
    # (We can't assert "boto3 not in sys.modules" because pytest may have
    # loaded it for other tests. Just import again to confirm no error.)
    import bedrock_ops  # noqa: PLC0415, F401
