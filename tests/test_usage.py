"""Token usage parsing tests."""

from __future__ import annotations

from bedrock_ops import (
    TokenUsage,
    aggregate_stream_usage,
    parse_converse_usage,
)


def test_parse_response_with_full_cache_fields() -> None:
    response = {
        "usage": {
            "inputTokens": 100,
            "outputTokens": 50,
            "cacheReadInputTokens": 800,
            "cacheWriteInputTokens": 200,
        }
    }
    usage = parse_converse_usage(response)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cache_read_input_tokens == 800
    assert usage.cache_write_input_tokens == 200
    assert usage.total_input_tokens == 1100
    assert usage.total_tokens == 1150


def test_parse_response_without_cache_fields_returns_zeros() -> None:
    response = {"usage": {"inputTokens": 50, "outputTokens": 10}}
    usage = parse_converse_usage(response)
    assert usage.cache_read_input_tokens == 0
    assert usage.cache_write_input_tokens == 0


def test_parse_response_missing_usage_returns_zero_usage() -> None:
    usage = parse_converse_usage({})
    assert usage == TokenUsage()


def test_cache_hit_rate_computed_correctly() -> None:
    usage = TokenUsage(input_tokens=10, cache_read_input_tokens=90)
    assert usage.cache_hit_rate == 0.9


def test_cache_hit_rate_handles_zero_input() -> None:
    assert TokenUsage().cache_hit_rate == 0.0


def test_token_usage_addition() -> None:
    a = TokenUsage(input_tokens=10, output_tokens=5, cache_read_input_tokens=3)
    b = TokenUsage(input_tokens=20, output_tokens=15, cache_write_input_tokens=7)
    c = a + b
    assert c.input_tokens == 30
    assert c.output_tokens == 20
    assert c.cache_read_input_tokens == 3
    assert c.cache_write_input_tokens == 7


def test_aggregate_stream_usage_from_metadata_events() -> None:
    events = [
        {"contentBlockDelta": {"delta": {"text": "hi"}}},
        {
            "metadata": {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 5,
                    "cacheReadInputTokens": 100,
                }
            }
        },
    ]
    usage = aggregate_stream_usage(events)
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert usage.cache_read_input_tokens == 100


def test_aggregate_stream_usage_sums_multiple_metadata_events() -> None:
    events = [
        {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5}}},
        {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 7}}},
    ]
    usage = aggregate_stream_usage(events)
    assert usage.input_tokens == 10
    assert usage.output_tokens == 12


def test_aggregate_stream_usage_empty_iterable() -> None:
    assert aggregate_stream_usage([]) == TokenUsage()
