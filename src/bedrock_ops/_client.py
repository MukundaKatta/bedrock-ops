"""Production-grade Bedrock Runtime client.

Composes the four bedrock-ops primitives:

1. **Throttle normalization** — botocore's retry handler matches throttle
   error codes case-sensitively, but Bedrock returns lowercase
   ``throttlingException`` from some paths (strands#905). The installed
   normalizer rewrites these to ``ThrottlingException`` so retries fire.

2. **Per-model read timeouts** — boto3's 60s default is too short for
   long-context Sonnet 4 calls (mem0#3825). Default raised to 120s; settable
   per-call via the ``read_timeout`` argument.

3. **Typed exceptions** — botocore exceptions are wrapped in the
   :mod:`bedrock_ops._errors` hierarchy so callers can ``except
   BedrockTimeout`` instead of inspecting traceback strings (boto3#4561).

4. **Full token usage** — :class:`TokenUsage` includes ``cacheReadInputTokens``
   and ``cacheWriteInputTokens`` that are dropped by other wrappers
   (strands#529).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    EventStreamError,
    ReadTimeoutError,
)

from ._errors import (
    BedrockOpsError,
    BedrockThrottled,
    BedrockTimeout,
    BedrockValidationError,
)
from ._guardrails import (
    GuardrailIntervention,
    check_guardrail_intervention,
)
from ._retry import install_throttle_normalizer, production_retry_config
from ._usage import TokenUsage, parse_converse_usage

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class ConverseResponse:
    """Typed view of a ``converse()`` response."""

    output_message: dict[str, Any]
    stop_reason: str
    usage: TokenUsage
    latency_ms: int
    guardrail: GuardrailIntervention | None
    raw: dict[str, Any]

    @property
    def text(self) -> str:
        """Concatenated text from all text content blocks in the output message."""
        parts: list[str] = []
        for block in self.output_message.get("content", []) or []:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts)

    @property
    def tool_uses(self) -> list[dict[str, Any]]:
        """All ``toolUse`` content blocks from the output message."""
        out: list[dict[str, Any]] = []
        for block in self.output_message.get("content", []) or []:
            if isinstance(block, dict):
                tu = block.get("toolUse")
                if isinstance(tu, dict):
                    out.append(tu)
        return out


class BedrockClient:
    """Production wrapper around ``boto3.client('bedrock-runtime')``."""

    def __init__(
        self,
        region_name: str | None = None,
        *,
        max_attempts: int = 5,
        retry_mode: str = "adaptive",
        connect_timeout: float = 10.0,
        read_timeout: float = 120.0,
        boto_session: Any | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        # Lazy import to keep top-level import cheap (cf. instructor#2205).
        import boto3  # noqa: PLC0415

        session = boto_session or boto3.session.Session()
        config = production_retry_config(
            max_attempts=max_attempts,
            mode=retry_mode,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        self._client = session.client(
            "bedrock-runtime",
            region_name=region_name,
            config=config,
            endpoint_url=endpoint_url,
        )
        install_throttle_normalizer(self._client)
        self._region = region_name or session.region_name or "us-east-1"
        self._max_attempts = max_attempts

    @property
    def raw(self) -> Any:
        """Underlying boto3 bedrock-runtime client. Use as an escape hatch."""
        return self._client

    def converse(
        self,
        *,
        modelId: str,
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]] | None = None,
        inferenceConfig: dict[str, Any] | None = None,
        toolConfig: dict[str, Any] | None = None,
        guardrailConfig: dict[str, Any] | None = None,
        additionalModelRequestFields: dict[str, Any] | None = None,
    ) -> ConverseResponse:
        """Call Bedrock Converse and return a typed response.

        Wraps botocore exceptions in :class:`BedrockOpsError` subclasses.
        Surfaces guardrail intervention as a non-content
        :class:`GuardrailIntervention` on the response (does not raise).
        Use :func:`bedrock_ops.assert_no_guardrail_violation` to opt into
        raising.
        """
        kwargs: dict[str, Any] = {
            "modelId": modelId,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if inferenceConfig is not None:
            kwargs["inferenceConfig"] = inferenceConfig
        if toolConfig is not None:
            kwargs["toolConfig"] = toolConfig
        if guardrailConfig is not None:
            kwargs["guardrailConfig"] = guardrailConfig
        if additionalModelRequestFields is not None:
            kwargs["additionalModelRequestFields"] = additionalModelRequestFields

        started = time.monotonic()
        try:
            response = self._client.converse(**kwargs)
        except ReadTimeoutError as e:
            elapsed = time.monotonic() - started
            raise BedrockTimeout(
                f"Bedrock read timed out after {elapsed:.1f}s",
                kind="read",
                elapsed_s=elapsed,
                endpoint=getattr(e, "endpoint_url", "") or "",
            ) from e
        except ConnectTimeoutError as e:
            elapsed = time.monotonic() - started
            raise BedrockTimeout(
                f"Bedrock connect timed out after {elapsed:.1f}s",
                kind="connect",
                elapsed_s=elapsed,
                endpoint=getattr(e, "endpoint_url", "") or "",
            ) from e
        except EndpointConnectionError as e:
            raise BedrockOpsError(f"Cannot reach Bedrock endpoint: {e}") from e
        except EventStreamError as e:
            raise BedrockOpsError(f"Bedrock event-stream error (connection released): {e}") from e
        except ClientError as e:
            self._wrap_client_error(e, model_id=modelId)
            raise  # pragma: no cover — _wrap_client_error always raises

        guardrail_id = (guardrailConfig or {}).get("guardrailIdentifier")
        intervention = (
            check_guardrail_intervention(response, guardrail_id=guardrail_id)
            if guardrail_id
            else None
        )

        return ConverseResponse(
            output_message=response.get("output", {}).get("message", {}),
            stop_reason=response.get("stopReason", ""),
            usage=parse_converse_usage(response),
            latency_ms=int(response.get("metrics", {}).get("latencyMs", 0)),
            guardrail=intervention,
            raw=response,
        )

    def converse_stream(
        self,
        *,
        modelId: str,
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]] | None = None,
        inferenceConfig: dict[str, Any] | None = None,
        toolConfig: dict[str, Any] | None = None,
        guardrailConfig: dict[str, Any] | None = None,
        additionalModelRequestFields: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Call Bedrock ConverseStream and yield raw events.

        v0.1 returns the raw event dicts so callers can use
        :func:`bedrock_ops.aggregate_stream_usage` to sum usage themselves.
        A normalized event taxonomy is planned for v0.2.
        """
        kwargs: dict[str, Any] = {
            "modelId": modelId,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if inferenceConfig is not None:
            kwargs["inferenceConfig"] = inferenceConfig
        if toolConfig is not None:
            kwargs["toolConfig"] = toolConfig
        if guardrailConfig is not None:
            kwargs["guardrailConfig"] = guardrailConfig
        if additionalModelRequestFields is not None:
            kwargs["additionalModelRequestFields"] = additionalModelRequestFields

        started = time.monotonic()
        try:
            response = self._client.converse_stream(**kwargs)
        except ReadTimeoutError as e:
            elapsed = time.monotonic() - started
            raise BedrockTimeout(
                f"Bedrock connect-phase read timed out after {elapsed:.1f}s",
                kind="read",
                elapsed_s=elapsed,
                endpoint=getattr(e, "endpoint_url", "") or "",
            ) from e
        except ClientError as e:
            self._wrap_client_error(e, model_id=modelId)
            raise  # pragma: no cover

        try:
            yield from response.get("stream", [])
        except EventStreamError as e:
            # boto3#4543: surface but do not let connection leak.
            raise BedrockOpsError(
                f"Bedrock stream interrupted (connection released): {e}"
            ) from e

    def _wrap_client_error(self, error: ClientError, *, model_id: str) -> None:
        code = error.response.get("Error", {}).get("Code", "")
        msg = error.response.get("Error", {}).get("Message", str(error))

        if code == "ThrottlingException":
            raise BedrockThrottled(
                f"Bedrock throttled after {self._max_attempts} attempts",
                region=self._region,
                model_id=model_id,
                attempts=self._max_attempts,
                original_code=code,
            ) from error
        if code == "ValidationException":
            raise BedrockValidationError(
                msg,
                model_id=model_id,
                request_field_path=None,
            ) from error

        # Other ClientErrors propagate through the BedrockOpsError base so
        # callers can have a single ``except BedrockOpsError`` net.
        raise BedrockOpsError(f"Bedrock {code}: {msg}") from error
