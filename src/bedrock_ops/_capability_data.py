"""Static capability table for Bedrock foundation models.

Sourced from AWS Bedrock model documentation as of 2026-04-30. Update via
``register_model()`` for newly-released models without waiting for a release.

Solves boto3#4206: no programmatic API to look up Bedrock model maxTokens or
feature support; AWS docs are scattered across many pages.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCapabilities:
    """What a Bedrock foundation model supports."""

    model_id: str
    family: str
    max_input_tokens: int
    max_output_tokens: int
    supports_vision: bool
    supports_tool_use: bool
    supports_prompt_cache: bool
    supports_thinking: bool
    supports_streaming: bool
    supports_cross_region_inference: bool
    available_regions: tuple[str, ...]


_US_REGIONS = ("us-east-1", "us-east-2", "us-west-2")
_US_PLUS_EU = (*_US_REGIONS, "eu-central-1", "eu-west-1", "eu-west-3")
_US_EU_AP = (*_US_PLUS_EU, "ap-southeast-1", "ap-northeast-1", "ap-south-1")


# Anthropic Claude family
_ANTHROPIC_MODELS: tuple[ModelCapabilities, ...] = (
    ModelCapabilities(
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        family="anthropic.claude",
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=True,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_EU_AP,
    ),
    ModelCapabilities(
        model_id="anthropic.claude-opus-4-20250514-v1:0",
        family="anthropic.claude",
        max_input_tokens=200_000,
        max_output_tokens=32_000,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=True,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
    ModelCapabilities(
        model_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
        family="anthropic.claude",
        max_input_tokens=200_000,
        max_output_tokens=64_000,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=True,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_PLUS_EU,
    ),
    ModelCapabilities(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        family="anthropic.claude",
        max_input_tokens=200_000,
        max_output_tokens=8_192,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_EU_AP,
    ),
    ModelCapabilities(
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        family="anthropic.claude",
        max_input_tokens=200_000,
        max_output_tokens=8_192,
        supports_vision=False,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
)


# Amazon Nova family
_NOVA_MODELS: tuple[ModelCapabilities, ...] = (
    ModelCapabilities(
        model_id="amazon.nova-pro-v1:0",
        family="amazon.nova",
        max_input_tokens=300_000,
        max_output_tokens=5_000,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
    ModelCapabilities(
        model_id="amazon.nova-lite-v1:0",
        family="amazon.nova",
        max_input_tokens=300_000,
        max_output_tokens=5_000,
        supports_vision=True,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
    ModelCapabilities(
        model_id="amazon.nova-micro-v1:0",
        family="amazon.nova",
        max_input_tokens=128_000,
        max_output_tokens=5_000,
        supports_vision=False,
        supports_tool_use=True,
        supports_prompt_cache=True,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
)


# Mistral family
_MISTRAL_MODELS: tuple[ModelCapabilities, ...] = (
    ModelCapabilities(
        model_id="mistral.mistral-large-2407-v1:0",
        family="mistral",
        max_input_tokens=128_000,
        max_output_tokens=8_192,
        supports_vision=False,
        supports_tool_use=True,
        supports_prompt_cache=False,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=False,
        available_regions=("us-west-2", "eu-west-3"),
    ),
)


# Meta Llama family
_LLAMA_MODELS: tuple[ModelCapabilities, ...] = (
    ModelCapabilities(
        model_id="meta.llama3-3-70b-instruct-v1:0",
        family="meta.llama",
        max_input_tokens=128_000,
        max_output_tokens=2_048,
        supports_vision=False,
        supports_tool_use=True,
        supports_prompt_cache=False,
        supports_thinking=False,
        supports_streaming=True,
        supports_cross_region_inference=True,
        available_regions=_US_REGIONS,
    ),
)


_TABLE: dict[str, ModelCapabilities] = {
    m.model_id: m
    for m in (*_ANTHROPIC_MODELS, *_NOVA_MODELS, *_MISTRAL_MODELS, *_LLAMA_MODELS)
}


_CROSS_REGION_PREFIXES: frozenset[str] = frozenset({"us", "eu", "apac", "us-gov"})


def _strip_cross_region_prefix(model_id: str) -> str:
    """Strip cross-region inference profile prefix (``us.``, ``eu.``, ``apac.``)."""
    head, sep, tail = model_id.partition(".")
    if sep and head in _CROSS_REGION_PREFIXES:
        return tail
    return model_id
