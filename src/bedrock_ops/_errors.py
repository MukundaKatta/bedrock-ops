"""Typed exception hierarchy for bedrock-ops.

Solves boto3#4561: ReadTimeoutError dumps full traceback to stderr instead of
returning a clean catchable error.
"""

from __future__ import annotations

from typing import Literal


class BedrockOpsError(Exception):
    """Base class for all bedrock-ops errors."""


class BedrockThrottled(BedrockOpsError):
    """Bedrock throttled the request after retries were exhausted."""

    def __init__(
        self,
        message: str,
        *,
        region: str,
        model_id: str,
        attempts: int,
        original_code: str,
    ) -> None:
        super().__init__(message)
        self.region = region
        self.model_id = model_id
        self.attempts = attempts
        self.original_code = original_code


class BedrockTimeout(BedrockOpsError):
    """Bedrock request timed out."""

    def __init__(
        self,
        message: str,
        *,
        kind: Literal["connect", "read"],
        elapsed_s: float,
        endpoint: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.elapsed_s = elapsed_s
        self.endpoint = endpoint


class BedrockGuardrailViolation(BedrockOpsError):
    """A configured Guardrail intervened on the request or response.

    Important: this exception deliberately does NOT carry the violating
    content. Logging the exception will not leak the PII / topic that
    triggered the rule. Callers that need the content for an authorized
    debug flow should pull it from the original response themselves.
    """

    def __init__(
        self,
        message: str,
        *,
        guardrail_id: str,
        action: Literal["BLOCKED", "ANONYMIZED"],
        intervened_on: Literal["input", "output"],
        categories: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.guardrail_id = guardrail_id
        self.action = action
        self.intervened_on = intervened_on
        self.categories = categories


class CapabilityUnknown(BedrockOpsError):
    """The given Bedrock model id has no entry in the capability table."""

    def __init__(self, model_id: str) -> None:
        super().__init__(
            f"No capability data for model_id={model_id!r}. "
            f"If this is a new model, add it via register_model() or open an issue."
        )
        self.model_id = model_id


class BedrockValidationError(BedrockOpsError):
    """Bedrock returned ValidationException — typically incompatible feature combos.

    Wraps boto3#4626 (latency-optimized + prompt cache) and similar.
    """

    def __init__(self, message: str, *, model_id: str, request_field_path: str | None = None) -> None:
        super().__init__(message)
        self.model_id = model_id
        self.request_field_path = request_field_path
