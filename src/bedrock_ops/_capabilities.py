"""Capability lookup API."""

from __future__ import annotations

from ._capability_data import (
    ModelCapabilities,
    _TABLE,
    _strip_cross_region_prefix,
)
from ._errors import BedrockValidationError, CapabilityUnknown


def capabilities(model_id: str) -> ModelCapabilities:
    """Look up capabilities for a Bedrock model id.

    Accepts both bare ids (``anthropic.claude-sonnet-4-20250514-v1:0``) and
    cross-region inference profile ids (``us.anthropic.claude-sonnet-4-...``).

    Raises :class:`CapabilityUnknown` if the model is not in the static table.
    """
    bare = _strip_cross_region_prefix(model_id)
    cap = _TABLE.get(bare)
    if cap is None:
        raise CapabilityUnknown(model_id)
    return cap


def register_model(cap: ModelCapabilities) -> None:
    """Add or replace a capability entry. Useful for new model releases."""
    _TABLE[cap.model_id] = cap


def precheck_features(
    model_id: str,
    *,
    use_prompt_cache: bool = False,
    use_thinking: bool = False,
    use_vision: bool = False,
    use_tool_use: bool = False,
    use_streaming: bool = False,
    region: str | None = None,
) -> None:
    """Validate a feature combination against the model's capabilities.

    Catches incompatibilities at call time instead of as a runtime
    ``ValidationException`` (boto3#4626).
    """
    cap = capabilities(model_id)
    missing: list[str] = []
    if use_prompt_cache and not cap.supports_prompt_cache:
        missing.append("prompt_cache")
    if use_thinking and not cap.supports_thinking:
        missing.append("thinking")
    if use_vision and not cap.supports_vision:
        missing.append("vision")
    if use_tool_use and not cap.supports_tool_use:
        missing.append("tool_use")
    if use_streaming and not cap.supports_streaming:
        missing.append("streaming")
    if missing:
        raise BedrockValidationError(
            f"Model {model_id!r} does not support: {', '.join(missing)}",
            model_id=model_id,
            request_field_path=None,
        )
    if region is not None and region not in cap.available_regions:
        raise BedrockValidationError(
            f"Model {model_id!r} is not available in region {region!r}. "
            f"Available: {', '.join(cap.available_regions)}",
            model_id=model_id,
            request_field_path="region",
        )
