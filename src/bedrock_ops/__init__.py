"""bedrock-ops — production-grade boto3 Bedrock toolkit.

Closes the eight gaps every team hits when running AWS Bedrock in production:
case-insensitive throttle retry, per-model timeouts, typed exceptions,
capability lookup, full token usage (including cache fields), and a
PII-safe Guardrails wrapper.

Quick start::

    from bedrock_ops import BedrockClient

    client = BedrockClient(region_name="us-east-1")
    resp = client.converse(
        modelId="anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": "hello"}]}],
    )
    print(resp.text, resp.usage.cache_hit_rate)
"""

from __future__ import annotations

from ._capabilities import (
    capabilities,
    precheck_features,
    register_model,
)
from ._capability_data import ModelCapabilities
from ._client import BedrockClient, ConverseResponse
from ._errors import (
    BedrockGuardrailViolation,
    BedrockOpsError,
    BedrockThrottled,
    BedrockTimeout,
    BedrockValidationError,
    CapabilityUnknown,
)
from ._guardrails import (
    GuardrailIntervention,
    REDACTED,
    assert_no_guardrail_violation,
    check_guardrail_intervention,
    repair_orphan_tool_uses,
    safe_log_response,
)
from ._retry import install_throttle_normalizer, production_retry_config
from ._usage import TokenUsage, aggregate_stream_usage, parse_converse_usage

__version__ = "0.1.0"

__all__ = [
    "BedrockClient",
    "BedrockGuardrailViolation",
    "BedrockOpsError",
    "BedrockThrottled",
    "BedrockTimeout",
    "BedrockValidationError",
    "CapabilityUnknown",
    "ConverseResponse",
    "GuardrailIntervention",
    "ModelCapabilities",
    "REDACTED",
    "TokenUsage",
    "__version__",
    "aggregate_stream_usage",
    "assert_no_guardrail_violation",
    "capabilities",
    "check_guardrail_intervention",
    "install_throttle_normalizer",
    "parse_converse_usage",
    "precheck_features",
    "production_retry_config",
    "register_model",
    "repair_orphan_tool_uses",
    "safe_log_response",
]
