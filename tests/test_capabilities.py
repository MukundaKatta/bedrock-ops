"""Capability lookup tests."""

from __future__ import annotations

import pytest

from bedrock_ops import (
    BedrockValidationError,
    CapabilityUnknown,
    ModelCapabilities,
    capabilities,
    precheck_features,
    register_model,
)


def test_lookup_anthropic_sonnet_4() -> None:
    cap = capabilities("anthropic.claude-sonnet-4-20250514-v1:0")
    assert cap.family == "anthropic.claude"
    assert cap.max_input_tokens == 200_000
    assert cap.supports_prompt_cache is True
    assert cap.supports_thinking is True
    assert cap.supports_vision is True


def test_lookup_with_us_cross_region_prefix_resolves() -> None:
    cap = capabilities("us.anthropic.claude-sonnet-4-20250514-v1:0")
    assert cap.model_id == "anthropic.claude-sonnet-4-20250514-v1:0"


def test_lookup_with_eu_cross_region_prefix_resolves() -> None:
    cap = capabilities("eu.anthropic.claude-3-7-sonnet-20250219-v1:0")
    assert cap.family == "anthropic.claude"


def test_lookup_unknown_model_raises_with_helpful_message() -> None:
    with pytest.raises(CapabilityUnknown) as exc_info:
        capabilities("bogus-model")
    assert "bogus-model" in str(exc_info.value)
    assert exc_info.value.model_id == "bogus-model"


def test_register_model_adds_to_table() -> None:
    new = ModelCapabilities(
        model_id="test.fake-model-v1:0",
        family="test",
        max_input_tokens=1000,
        max_output_tokens=100,
        supports_vision=False,
        supports_tool_use=False,
        supports_prompt_cache=False,
        supports_thinking=False,
        supports_streaming=False,
        supports_cross_region_inference=False,
        available_regions=("us-east-1",),
    )
    register_model(new)
    assert capabilities("test.fake-model-v1:0").max_input_tokens == 1000


def test_precheck_passes_for_supported_features() -> None:
    precheck_features(
        "anthropic.claude-sonnet-4-20250514-v1:0",
        use_prompt_cache=True,
        use_thinking=True,
        use_tool_use=True,
        use_vision=True,
        use_streaming=True,
        region="us-east-1",
    )


def test_precheck_raises_when_thinking_unsupported() -> None:
    with pytest.raises(BedrockValidationError) as exc_info:
        precheck_features(
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            use_thinking=True,
        )
    assert "thinking" in str(exc_info.value)


def test_precheck_raises_when_region_unavailable() -> None:
    with pytest.raises(BedrockValidationError) as exc_info:
        precheck_features(
            "anthropic.claude-opus-4-20250514-v1:0",
            region="ap-south-1",
        )
    assert "ap-south-1" in str(exc_info.value)
    assert exc_info.value.request_field_path == "region"


def test_precheck_raises_when_vision_unsupported() -> None:
    with pytest.raises(BedrockValidationError):
        precheck_features("anthropic.claude-3-5-haiku-20241022-v1:0", use_vision=True)
