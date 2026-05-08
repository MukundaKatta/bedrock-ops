"""Guardrails wrapper tests, with focus on the no-PII-leak invariant."""

from __future__ import annotations

import pytest

from bedrock_ops import (
    BedrockGuardrailViolation,
    REDACTED,
    assert_no_guardrail_violation,
    check_guardrail_intervention,
    repair_orphan_tool_uses,
    safe_log_response,
)


PII_STRING = "SSN 123-45-6789 and email alice@example.com"


def _response_with_guardrail_block(*, guardrail_id: str, pii: str) -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": pii}],
            }
        },
        "stopReason": "guardrail_intervened",
        "usage": {"inputTokens": 10, "outputTokens": 20},
        "trace": {
            "guardrail": {
                "outputAssessments": {
                    guardrail_id: [
                        {
                            "sensitiveInformationPolicy": {
                                "piiEntities": [
                                    {
                                        "type": "EMAIL",
                                        "match": pii,
                                        "action": "BLOCKED",
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        },
    }


def test_no_intervention_returns_none() -> None:
    response = {"output": {"message": {"content": []}}, "stopReason": "end_turn"}
    assert check_guardrail_intervention(response, guardrail_id="gid") is None


def test_intervention_returns_categories_without_content() -> None:
    response = _response_with_guardrail_block(guardrail_id="gid", pii=PII_STRING)
    intervention = check_guardrail_intervention(response, guardrail_id="gid")
    assert intervention is not None
    assert intervention.action == "BLOCKED"
    assert intervention.intervened_on == "output"
    assert "sensitiveInformationPolicy" in intervention.categories
    # Critical: the dataclass has no field that contains PII
    for value in intervention.__dict__.values():
        assert PII_STRING not in str(value)


def test_assert_raises_with_no_pii_in_exception() -> None:
    response = _response_with_guardrail_block(guardrail_id="gid", pii=PII_STRING)
    with pytest.raises(BedrockGuardrailViolation) as exc_info:
        assert_no_guardrail_violation(response, guardrail_id="gid")
    # Exception text and attrs must not contain the PII
    assert PII_STRING not in str(exc_info.value)
    assert PII_STRING not in repr(exc_info.value)
    for value in vars(exc_info.value).values():
        assert PII_STRING not in str(value)


def test_safe_log_response_redacts_output_when_intervened() -> None:
    response = _response_with_guardrail_block(guardrail_id="gid", pii=PII_STRING)
    safe = safe_log_response(response, guardrail_id="gid")
    assert PII_STRING not in str(safe)
    output_text = safe["output"]["message"]["content"][0]["text"]
    assert output_text == REDACTED
    # Original is not mutated
    assert response["output"]["message"]["content"][0]["text"] == PII_STRING


def test_safe_log_response_strips_trace_when_intervened() -> None:
    response = _response_with_guardrail_block(guardrail_id="gid", pii=PII_STRING)
    safe = safe_log_response(response, guardrail_id="gid")
    assert "redacted_by" in safe["trace"]["guardrail"]
    assert PII_STRING not in str(safe["trace"])


def test_safe_log_response_no_intervention_returns_unchanged() -> None:
    response = {"output": {"message": {"content": [{"text": "ok"}]}}, "stopReason": "end_turn"}
    safe = safe_log_response(response, guardrail_id="gid")
    assert safe == response


def test_safe_log_response_with_no_guardrail_id_returns_unchanged() -> None:
    response = _response_with_guardrail_block(guardrail_id="gid", pii=PII_STRING)
    safe = safe_log_response(response, guardrail_id=None)
    assert safe == response


def test_repair_drops_orphan_tool_use_when_result_missing() -> None:
    messages = [
        {"role": "user", "content": [{"text": "what's the weather?"}]},
        {
            "role": "assistant",
            "content": [
                {"text": "calling weather"},
                {"toolUse": {"toolUseId": "tu_1", "name": "get_weather", "input": {}}},
                {"toolUse": {"toolUseId": "tu_2", "name": "get_news", "input": {}}},
            ],
        },
        # Only tu_2's result is present (tu_1 was redacted by Guardrails)
        {
            "role": "user",
            "content": [
                {"toolResult": {"toolUseId": "tu_2", "content": [{"text": "headlines..."}]}},
            ],
        },
    ]
    repaired = repair_orphan_tool_uses(messages)
    # tu_1 should be gone, tu_2 should remain
    assistant_blocks = repaired[1]["content"]
    tool_use_ids = [b["toolUse"]["toolUseId"] for b in assistant_blocks if "toolUse" in b]
    assert tool_use_ids == ["tu_2"]
    # text block survives
    assert any("text" in b for b in assistant_blocks)


def test_repair_is_pure_does_not_mutate_input() -> None:
    messages = [
        {
            "role": "assistant",
            "content": [{"toolUse": {"toolUseId": "tu_1", "name": "x", "input": {}}}],
        }
    ]
    repaired = repair_orphan_tool_uses(messages)
    assert messages[0]["content"][0]["toolUse"]["toolUseId"] == "tu_1"
    assert repaired[0]["content"] == []


def test_repair_keeps_messages_with_no_orphans_intact() -> None:
    messages = [
        {"role": "user", "content": [{"text": "hi"}]},
        {"role": "assistant", "content": [{"text": "hello"}]},
    ]
    assert repair_orphan_tool_uses(messages) == messages
