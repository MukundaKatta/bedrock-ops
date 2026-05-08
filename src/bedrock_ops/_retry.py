"""Throttle-code normalization for botocore retry handlers.

Bedrock returns throttling errors with multiple inconsistent error codes,
including lowercase variants like ``throttlingException`` (strands#905) and
``EventStreamError`` for streaming throttles (boto3#4543, closed-not-planned).
botocore's retry handler matches these case-sensitively against a fixed list,
so legitimate throttle responses go un-retried and surface raw to the caller.

This module installs a botocore event hook that normalizes any recognized
throttle code to ``ThrottlingException`` before the retry handler inspects it.
"""

from __future__ import annotations

from typing import Any

from botocore.config import Config

# Lowercase forms of every throttle-shaped error code we've seen returned by
# bedrock-runtime, bedrock-agent-runtime, or wrapping streaming layers.
_THROTTLE_CODES_LOWERCASE: frozenset[str] = frozenset(
    {
        "throttling",
        "throttlingexception",
        "throttledexception",
        "toomanyrequestsexception",
        "requestthrottledexception",
        "provisionedthroughputexceededexception",
        "throttled",
        "limitexceededexception",
        "modelnotreadyexception",
    }
)

_CANONICAL = "ThrottlingException"


def _normalize_after_call(parsed: dict[str, Any], **_: Any) -> None:
    """Rewrite recognized throttle error codes to their canonical form.

    Registered as an ``after-call.*`` hook so botocore's retry checker sees
    the canonical code on the next iteration.
    """
    error = parsed.get("Error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        return
    code = error.get("Code")
    if not isinstance(code, str) or code == _CANONICAL:
        return
    if code.lower() in _THROTTLE_CODES_LOWERCASE:
        error["Code"] = _CANONICAL


def install_throttle_normalizer(client: Any) -> None:
    """Register the throttle-code normalizer on a boto3 bedrock client."""
    events = client.meta.events
    events.register("after-call.bedrock-runtime", _normalize_after_call)
    events.register("after-call.bedrock-agent-runtime", _normalize_after_call)


def production_retry_config(
    *,
    max_attempts: int = 5,
    mode: str = "adaptive",
    connect_timeout: float = 10.0,
    read_timeout: float = 120.0,
) -> Config:
    """Botocore Config tuned for Bedrock production workloads.

    - ``adaptive`` retry mode reacts to bedrock's burst-and-token-bucket throttling.
    - ``connect_timeout`` 10s catches truly-down endpoints quickly.
    - ``read_timeout`` 120s is the default for long-context Sonnet 4 calls (mem0#3825).
      Override per-model via :class:`bedrock_ops.BedrockClient`.
    """
    return Config(
        retries={"max_attempts": max_attempts, "mode": mode},
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
