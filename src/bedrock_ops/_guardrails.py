"""Guardrail wrapper that does not leak PII into logs.

Solves litellm#12152: when a Bedrock Guardrail with
``SensitiveInformationPolicyConfig`` (PII) intervenes, the violating content
appears in the API response. Many wrapper libraries log the full response,
which reproduces the very PII the Guardrail was meant to suppress in the
log stream and any downstream tracing DB.

Solves strands-agents#1077: ``guardrail_redact_input=True`` redacts
tool_results in conversation history but leaves the matching ``tool_use``
blocks orphaned, breaking the next turn's API validation.

This module provides three primitives:

- :func:`check_guardrail_intervention`: detect intervention without
  capturing content.
- :func:`safe_log_response`: return a redacted copy of the response safe to
  send to a structured logger.
- :func:`repair_orphan_tool_uses`: drop ``tool_use`` blocks whose
  ``tool_result`` was redacted, restoring a valid Bedrock message structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ._errors import BedrockGuardrailViolation


REDACTED = "[REDACTED-by-bedrock-ops]"


@dataclass(frozen=True)
class GuardrailIntervention:
    """A non-content record of guardrail action.

    Notably absent: the violating text. Storing the categories that fired
    is enough for routing and metrics; the original content stays in the
    raw response and never propagates through this object.
    """

    guardrail_id: str
    action: Literal["BLOCKED", "ANONYMIZED"]
    intervened_on: Literal["input", "output"]
    categories: tuple[str, ...]


_FILTER_TYPES: tuple[str, ...] = (
    "topicPolicy",
    "contentPolicy",
    "wordPolicy",
    "sensitiveInformationPolicy",
    "contextualGroundingPolicy",
)


def _categories_from_assessments(assessments: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for a in assessments:
        for ft in _FILTER_TYPES:
            if ft in a:
                found.add(ft)
    return found


def check_guardrail_intervention(
    response: dict[str, Any],
    *,
    guardrail_id: str,
) -> GuardrailIntervention | None:
    """Inspect a Converse response for guardrail action.

    Returns ``None`` if no intervention occurred. Returns a
    :class:`GuardrailIntervention` (containing only categories, not content)
    otherwise.
    """
    trace = response.get("trace") or {}
    guardrail = trace.get("guardrail") or {}
    if not guardrail:
        return None

    output_assessments_map = guardrail.get("outputAssessments") or {}
    input_assessments_map = guardrail.get("inputAssessment") or {}

    output_for_id = output_assessments_map.get(guardrail_id) or []
    input_for_id = input_assessments_map.get(guardrail_id) or {}

    if not output_for_id and not input_for_id:
        return None

    stop_reason = response.get("stopReason", "")
    if stop_reason in {"guardrail_intervened", "GUARDRAIL_INTERVENED"}:
        action: Literal["BLOCKED", "ANONYMIZED"] = "BLOCKED"
    else:
        action = "ANONYMIZED"

    if output_for_id:
        intervened_on: Literal["input", "output"] = "output"
        categories = _categories_from_assessments(output_for_id)
    else:
        intervened_on = "input"
        categories = _categories_from_assessments([input_for_id])

    return GuardrailIntervention(
        guardrail_id=guardrail_id,
        action=action,
        intervened_on=intervened_on,
        categories=tuple(sorted(categories)),
    )


def assert_no_guardrail_violation(
    response: dict[str, Any],
    *,
    guardrail_id: str,
) -> None:
    """Raise :class:`BedrockGuardrailViolation` if the guardrail intervened.

    The exception carries categories but never content, so logging or
    tracing the exception will not leak PII.
    """
    intervention = check_guardrail_intervention(response, guardrail_id=guardrail_id)
    if intervention is None:
        return
    raise BedrockGuardrailViolation(
        f"Guardrail {guardrail_id} {intervention.action.lower()} on {intervention.intervened_on}; "
        f"categories={list(intervention.categories)}",
        guardrail_id=guardrail_id,
        action=intervention.action,
        intervened_on=intervention.intervened_on,
        categories=intervention.categories,
    )


def safe_log_response(
    response: dict[str, Any],
    *,
    guardrail_id: str | None = None,
) -> dict[str, Any]:
    """Return a deep-ish copy of the response safe to emit to a logger.

    If a guardrail intervened, all model output text in the copy is
    replaced with ``[REDACTED-by-bedrock-ops]``. The original response is
    not mutated. When ``guardrail_id`` is None, the response is returned
    unchanged (caller opted out of redaction).
    """
    if guardrail_id is None:
        return response

    intervention = check_guardrail_intervention(response, guardrail_id=guardrail_id)
    if intervention is None:
        return response

    safe = dict(response)
    output = safe.get("output")
    if isinstance(output, dict):
        message = output.get("message")
        if isinstance(message, dict):
            safe["output"] = {
                **output,
                "message": {
                    "role": message.get("role", "assistant"),
                    "content": [{"text": REDACTED}],
                },
            }
    # Strip the trace too — it can also contain matched substrings.
    if "trace" in safe:
        safe = {k: v for k, v in safe.items() if k != "trace"}
        safe["trace"] = {"guardrail": {"redacted_by": "bedrock-ops"}}
    return safe


def repair_orphan_tool_uses(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop ``tool_use`` content blocks whose matching ``tool_result`` is missing.

    When ``guardrail_redact_input=True`` strips a tool_result from history,
    the matching tool_use is left orphaned and the next Converse call
    fails with a validation error. This function returns a new message list
    with the orphaned tool_use blocks removed. Pure function; the input
    is not mutated.
    """
    have_tool_results: set[str] = set()
    for msg in messages:
        for block in msg.get("content", []) or []:
            if isinstance(block, dict):
                tr = block.get("toolResult")
                if isinstance(tr, dict):
                    use_id = tr.get("toolUseId")
                    if isinstance(use_id, str):
                        have_tool_results.add(use_id)

    repaired: list[dict[str, Any]] = []
    for msg in messages:
        new_content: list[Any] = []
        for block in msg.get("content", []) or []:
            if isinstance(block, dict):
                tu = block.get("toolUse")
                if isinstance(tu, dict):
                    use_id = tu.get("toolUseId")
                    if isinstance(use_id, str) and use_id not in have_tool_results:
                        continue
            new_content.append(block)
        repaired.append({**msg, "content": new_content})
    return repaired
