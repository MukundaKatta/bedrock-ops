"""Standard-library ``unittest`` suite for the boto3-free core.

These tests exercise the real ``bedrock_ops`` code with **zero third-party
dependencies** — no ``pytest``, no ``boto3``, no ``botocore`` — so they can run
in any minimal Python 3.10+ environment via::

    python3 -m unittest discover -s tests/stdlib

The richer ``pytest`` suite under ``tests/`` (which mocks ``boto3`` and covers
``BedrockClient``) remains the primary, coverage-gated test run. This suite is
a fast, install-free smoke test of the pure logic and adds coverage for a
number of edge cases the pytest suite does not assert (the ``apac.`` cross
-region prefix, ``TokenUsage.__add__`` returning ``NotImplemented`` for foreign
operands, the ANONYMIZED guardrail action, input-side guardrail interventions,
and capability-table invariants).
"""

from __future__ import annotations

import unittest

from _bootstrap import load_pure_modules

_M = load_pure_modules()

TokenUsage = _M["TokenUsage"]
parse_converse_usage = _M["parse_converse_usage"]
aggregate_stream_usage = _M["aggregate_stream_usage"]

capabilities = _M["capabilities"]
register_model = _M["register_model"]
precheck_features = _M["precheck_features"]
ModelCapabilities = _M["ModelCapabilities"]
_TABLE = _M["_TABLE"]
_strip_cross_region_prefix = _M["_strip_cross_region_prefix"]

check_guardrail_intervention = _M["check_guardrail_intervention"]
assert_no_guardrail_violation = _M["assert_no_guardrail_violation"]
safe_log_response = _M["safe_log_response"]
repair_orphan_tool_uses = _M["repair_orphan_tool_uses"]
REDACTED = _M["REDACTED"]

BedrockOpsError = _M["BedrockOpsError"]
BedrockThrottled = _M["BedrockThrottled"]
BedrockTimeout = _M["BedrockTimeout"]
BedrockGuardrailViolation = _M["BedrockGuardrailViolation"]
BedrockValidationError = _M["BedrockValidationError"]
CapabilityUnknown = _M["CapabilityUnknown"]


PII_STRING = "SSN 123-45-6789 and email alice@example.com"


class TokenUsageTests(unittest.TestCase):
    def test_parse_full_cache_fields(self) -> None:
        usage = parse_converse_usage(
            {
                "usage": {
                    "inputTokens": 100,
                    "outputTokens": 50,
                    "cacheReadInputTokens": 800,
                    "cacheWriteInputTokens": 200,
                }
            }
        )
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.cache_read_input_tokens, 800)
        self.assertEqual(usage.cache_write_input_tokens, 200)
        self.assertEqual(usage.total_input_tokens, 1100)
        self.assertEqual(usage.total_tokens, 1150)

    def test_parse_missing_usage_is_all_zero(self) -> None:
        self.assertEqual(parse_converse_usage({}), TokenUsage())

    def test_parse_tolerates_null_field_values(self) -> None:
        # Some wrappers emit explicit None for absent counters.
        usage = parse_converse_usage(
            {"usage": {"inputTokens": None, "outputTokens": 7, "cacheReadInputTokens": None}}
        )
        self.assertEqual(usage.input_tokens, 0)
        self.assertEqual(usage.output_tokens, 7)
        self.assertEqual(usage.cache_read_input_tokens, 0)

    def test_cache_hit_rate(self) -> None:
        self.assertAlmostEqual(
            TokenUsage(input_tokens=10, cache_read_input_tokens=90).cache_hit_rate,
            0.9,
        )

    def test_cache_hit_rate_zero_input_is_zero_not_error(self) -> None:
        self.assertEqual(TokenUsage().cache_hit_rate, 0.0)

    def test_cache_hit_rate_counts_writes_in_denominator(self) -> None:
        # A pure cache *write* (first call) is not a hit: rate must be 0.
        usage = TokenUsage(input_tokens=0, cache_read_input_tokens=0, cache_write_input_tokens=500)
        self.assertEqual(usage.total_input_tokens, 500)
        self.assertEqual(usage.cache_hit_rate, 0.0)

    def test_addition_sums_all_fields(self) -> None:
        a = TokenUsage(input_tokens=10, output_tokens=5, cache_read_input_tokens=3)
        b = TokenUsage(input_tokens=20, output_tokens=15, cache_write_input_tokens=7)
        c = a + b
        self.assertEqual(c.input_tokens, 30)
        self.assertEqual(c.output_tokens, 20)
        self.assertEqual(c.cache_read_input_tokens, 3)
        self.assertEqual(c.cache_write_input_tokens, 7)

    def test_addition_with_non_tokenusage_returns_notimplemented(self) -> None:
        # __add__ must defer (return NotImplemented) so Python can try the
        # other operand's __radd__ / raise TypeError instead of crashing.
        self.assertIs(TokenUsage().__add__(42), NotImplemented)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            _ = TokenUsage() + 1  # type: ignore[operator]

    def test_is_frozen(self) -> None:
        usage = TokenUsage(input_tokens=1)
        with self.assertRaises(Exception):
            usage.input_tokens = 2  # type: ignore[misc]

    def test_aggregate_sums_multiple_metadata_events(self) -> None:
        events = [
            {"contentBlockDelta": {"delta": {"text": "hi"}}},
            {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 100}}},
            {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 7}}},
        ]
        usage = aggregate_stream_usage(events)
        self.assertEqual(usage.input_tokens, 10)
        self.assertEqual(usage.output_tokens, 12)
        self.assertEqual(usage.cache_read_input_tokens, 100)

    def test_aggregate_empty_is_zero(self) -> None:
        self.assertEqual(aggregate_stream_usage([]), TokenUsage())

    def test_aggregate_ignores_events_without_usage(self) -> None:
        events = [{"metadata": {}}, {"messageStop": {"stopReason": "end_turn"}}]
        self.assertEqual(aggregate_stream_usage(events), TokenUsage())


class CapabilityTests(unittest.TestCase):
    def test_bare_lookup(self) -> None:
        cap = capabilities("anthropic.claude-sonnet-4-20250514-v1:0")
        self.assertEqual(cap.family, "anthropic.claude")
        self.assertEqual(cap.max_input_tokens, 200_000)
        self.assertTrue(cap.supports_thinking)

    def test_us_prefix_resolves_to_bare_model(self) -> None:
        cap = capabilities("us.anthropic.claude-sonnet-4-20250514-v1:0")
        self.assertEqual(cap.model_id, "anthropic.claude-sonnet-4-20250514-v1:0")

    def test_apac_prefix_resolves(self) -> None:
        # apac. is a real Bedrock inference-profile prefix the pytest suite
        # does not cover.
        cap = capabilities("apac.anthropic.claude-sonnet-4-20250514-v1:0")
        self.assertEqual(cap.model_id, "anthropic.claude-sonnet-4-20250514-v1:0")

    def test_strip_prefix_leaves_unknown_prefix_untouched(self) -> None:
        # "amazon" is a vendor segment, not a region prefix: must NOT be stripped.
        self.assertEqual(
            _strip_cross_region_prefix("amazon.nova-pro-v1:0"),
            "amazon.nova-pro-v1:0",
        )

    def test_strip_prefix_on_id_without_dot(self) -> None:
        self.assertEqual(_strip_cross_region_prefix("noseparator"), "noseparator")

    def test_unknown_model_raises_with_id_in_message(self) -> None:
        with self.assertRaises(CapabilityUnknown) as ctx:
            capabilities("totally-made-up-model")
        self.assertIn("totally-made-up-model", str(ctx.exception))
        self.assertEqual(ctx.exception.model_id, "totally-made-up-model")

    def test_register_then_lookup_roundtrips(self) -> None:
        cap = ModelCapabilities(
            model_id="test.stdlib-fake-v1:0",
            family="test",
            max_input_tokens=1234,
            max_output_tokens=99,
            supports_vision=False,
            supports_tool_use=False,
            supports_prompt_cache=False,
            supports_thinking=False,
            supports_streaming=False,
            supports_cross_region_inference=False,
            available_regions=("us-east-1",),
        )
        try:
            register_model(cap)
            self.assertEqual(capabilities("test.stdlib-fake-v1:0").max_input_tokens, 1234)
        finally:
            _TABLE.pop("test.stdlib-fake-v1:0", None)

    def test_precheck_all_supported_passes(self) -> None:
        # Should not raise.
        precheck_features(
            "anthropic.claude-sonnet-4-20250514-v1:0",
            use_prompt_cache=True,
            use_thinking=True,
            use_tool_use=True,
            use_vision=True,
            use_streaming=True,
            region="us-east-1",
        )

    def test_precheck_unsupported_thinking_raises(self) -> None:
        with self.assertRaises(BedrockValidationError) as ctx:
            precheck_features("anthropic.claude-3-5-sonnet-20241022-v2:0", use_thinking=True)
        self.assertIn("thinking", str(ctx.exception))

    def test_precheck_reports_all_missing_features(self) -> None:
        # Mistral Large supports neither prompt cache nor thinking; both must
        # appear in a single error message.
        with self.assertRaises(BedrockValidationError) as ctx:
            precheck_features(
                "mistral.mistral-large-2407-v1:0",
                use_prompt_cache=True,
                use_thinking=True,
            )
        msg = str(ctx.exception)
        self.assertIn("prompt_cache", msg)
        self.assertIn("thinking", msg)

    def test_precheck_unavailable_region_raises_with_field_path(self) -> None:
        with self.assertRaises(BedrockValidationError) as ctx:
            precheck_features("anthropic.claude-opus-4-20250514-v1:0", region="ap-south-1")
        self.assertEqual(ctx.exception.request_field_path, "region")
        self.assertIn("ap-south-1", str(ctx.exception))

    def test_precheck_unknown_model_raises_capability_unknown(self) -> None:
        with self.assertRaises(CapabilityUnknown):
            precheck_features("no-such-model", use_vision=True)


class CapabilityTableInvariantTests(unittest.TestCase):
    """Data-integrity checks over the static capability table."""

    def test_table_is_not_empty(self) -> None:
        self.assertGreater(len(_TABLE), 0)

    def test_every_entry_key_matches_its_model_id(self) -> None:
        for key, cap in _TABLE.items():
            self.assertEqual(key, cap.model_id)

    def test_token_limits_are_positive(self) -> None:
        for cap in _TABLE.values():
            self.assertGreater(cap.max_input_tokens, 0, cap.model_id)
            self.assertGreater(cap.max_output_tokens, 0, cap.model_id)

    def test_every_entry_lists_at_least_one_region(self) -> None:
        for cap in _TABLE.values():
            self.assertGreaterEqual(len(cap.available_regions), 1, cap.model_id)

    def test_capabilities_returns_for_every_table_entry(self) -> None:
        for model_id in _TABLE:
            self.assertEqual(capabilities(model_id).model_id, model_id)


class GuardrailTests(unittest.TestCase):
    @staticmethod
    def _blocked_output_response(*, guardrail_id: str, pii: str) -> dict:
        return {
            "output": {"message": {"role": "assistant", "content": [{"text": pii}]}},
            "stopReason": "guardrail_intervened",
            "usage": {"inputTokens": 10, "outputTokens": 20},
            "trace": {
                "guardrail": {
                    "outputAssessments": {
                        guardrail_id: [
                            {
                                "sensitiveInformationPolicy": {
                                    "piiEntities": [
                                        {"type": "EMAIL", "match": pii, "action": "BLOCKED"}
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
        }

    def test_no_intervention_returns_none(self) -> None:
        response = {"output": {"message": {"content": []}}, "stopReason": "end_turn"}
        self.assertIsNone(check_guardrail_intervention(response, guardrail_id="gid"))

    def test_intervention_carries_categories_not_content(self) -> None:
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        intervention = check_guardrail_intervention(response, guardrail_id="gid")
        self.assertIsNotNone(intervention)
        assert intervention is not None  # for type-checkers
        self.assertEqual(intervention.action, "BLOCKED")
        self.assertEqual(intervention.intervened_on, "output")
        self.assertIn("sensitiveInformationPolicy", intervention.categories)
        for value in intervention.__dict__.values():
            self.assertNotIn(PII_STRING, str(value))

    def test_input_side_intervention_detected(self) -> None:
        # Input assessments live under a different key than output ones; the
        # pytest suite only covers the output path.
        response = {
            "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
            "stopReason": "end_turn",
            "trace": {
                "guardrail": {
                    "inputAssessment": {
                        "gid": {"topicPolicy": {"topics": [{"name": "medical"}]}}
                    }
                }
            },
        }
        intervention = check_guardrail_intervention(response, guardrail_id="gid")
        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(intervention.intervened_on, "input")
        self.assertIn("topicPolicy", intervention.categories)

    def test_anonymized_action_when_no_block_stop_reason(self) -> None:
        # A guardrail assessment present but stopReason != guardrail_intervened
        # means content was anonymized, not blocked.
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        response["stopReason"] = "end_turn"
        intervention = check_guardrail_intervention(response, guardrail_id="gid")
        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(intervention.action, "ANONYMIZED")

    def test_assessment_for_other_guardrail_id_is_ignored(self) -> None:
        response = self._blocked_output_response(guardrail_id="other-gid", pii=PII_STRING)
        self.assertIsNone(check_guardrail_intervention(response, guardrail_id="gid"))

    def test_assert_raises_without_pii_in_exception(self) -> None:
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        with self.assertRaises(BedrockGuardrailViolation) as ctx:
            assert_no_guardrail_violation(response, guardrail_id="gid")
        self.assertNotIn(PII_STRING, str(ctx.exception))
        self.assertNotIn(PII_STRING, repr(ctx.exception))
        for value in vars(ctx.exception).values():
            self.assertNotIn(PII_STRING, str(value))

    def test_assert_passes_when_no_intervention(self) -> None:
        response = {"output": {"message": {"content": [{"text": "ok"}]}}, "stopReason": "end_turn"}
        # Should not raise.
        assert_no_guardrail_violation(response, guardrail_id="gid")

    def test_safe_log_redacts_output_and_preserves_original(self) -> None:
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        safe = safe_log_response(response, guardrail_id="gid")
        self.assertNotIn(PII_STRING, str(safe))
        self.assertEqual(safe["output"]["message"]["content"][0]["text"], REDACTED)
        # Input untouched.
        self.assertEqual(response["output"]["message"]["content"][0]["text"], PII_STRING)

    def test_safe_log_strips_trace(self) -> None:
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        safe = safe_log_response(response, guardrail_id="gid")
        self.assertIn("redacted_by", safe["trace"]["guardrail"])
        self.assertNotIn(PII_STRING, str(safe["trace"]))

    def test_safe_log_no_guardrail_id_returns_input_unchanged(self) -> None:
        response = self._blocked_output_response(guardrail_id="gid", pii=PII_STRING)
        self.assertIs(safe_log_response(response, guardrail_id=None), response)

    def test_safe_log_no_intervention_returns_input_unchanged(self) -> None:
        response = {"output": {"message": {"content": [{"text": "ok"}]}}, "stopReason": "end_turn"}
        self.assertEqual(safe_log_response(response, guardrail_id="gid"), response)


class RepairOrphanToolUsesTests(unittest.TestCase):
    def test_drops_only_orphaned_tool_use(self) -> None:
        messages = [
            {"role": "user", "content": [{"text": "weather?"}]},
            {
                "role": "assistant",
                "content": [
                    {"text": "calling tools"},
                    {"toolUse": {"toolUseId": "tu_1", "name": "get_weather", "input": {}}},
                    {"toolUse": {"toolUseId": "tu_2", "name": "get_news", "input": {}}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "tu_2", "content": [{"text": "news"}]}}
                ],
            },
        ]
        repaired = repair_orphan_tool_uses(messages)
        assistant_blocks = repaired[1]["content"]
        ids = [b["toolUse"]["toolUseId"] for b in assistant_blocks if "toolUse" in b]
        self.assertEqual(ids, ["tu_2"])
        self.assertTrue(any("text" in b for b in assistant_blocks))

    def test_is_pure_does_not_mutate_input(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": [{"toolUse": {"toolUseId": "tu_1", "name": "x", "input": {}}}],
            }
        ]
        repaired = repair_orphan_tool_uses(messages)
        # Input intact, output stripped.
        self.assertEqual(messages[0]["content"][0]["toolUse"]["toolUseId"], "tu_1")
        self.assertEqual(repaired[0]["content"], [])

    def test_no_orphans_returns_equal_structure(self) -> None:
        messages = [
            {"role": "user", "content": [{"text": "hi"}]},
            {"role": "assistant", "content": [{"text": "hello"}]},
        ]
        self.assertEqual(repair_orphan_tool_uses(messages), messages)

    def test_handles_messages_with_no_content_key(self) -> None:
        messages = [{"role": "user"}]
        self.assertEqual(repair_orphan_tool_uses(messages), [{"role": "user", "content": []}])


class ErrorHierarchyTests(unittest.TestCase):
    def test_all_errors_subclass_base(self) -> None:
        for exc in (
            BedrockThrottled,
            BedrockTimeout,
            BedrockGuardrailViolation,
            BedrockValidationError,
            CapabilityUnknown,
        ):
            self.assertTrue(issubclass(exc, BedrockOpsError), exc.__name__)

    def test_throttled_carries_diagnostics(self) -> None:
        err = BedrockThrottled(
            "boom",
            region="us-east-1",
            model_id="m",
            attempts=5,
            original_code="throttlingException",
        )
        self.assertEqual(err.region, "us-east-1")
        self.assertEqual(err.attempts, 5)
        self.assertEqual(err.original_code, "throttlingException")

    def test_timeout_carries_kind_and_elapsed(self) -> None:
        err = BedrockTimeout("slow", kind="read", elapsed_s=12.5, endpoint="https://x")
        self.assertEqual(err.kind, "read")
        self.assertEqual(err.elapsed_s, 12.5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
