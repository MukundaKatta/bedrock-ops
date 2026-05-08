"""Token usage including Bedrock cache fields.

Solves strands-agents#529 (cacheReadInputTokens / cacheWriteInputTokens
silently dropped from Strands' Usage class) and llama_index#19293
(Gemini-style models lose token counts entirely).

Bedrock's Converse API returns four token fields when prompt caching is in
play:
- ``inputTokens``: non-cached prompt tokens
- ``cacheReadInputTokens``: prompt tokens served from cache (90% discount)
- ``cacheWriteInputTokens``: prompt tokens written to cache this call
- ``outputTokens``: model output

A cache *hit* means input tokens went to ``cacheReadInputTokens``; a cache
*write* means the same tokens went to ``cacheWriteInputTokens`` (one-time
cost). Without surfacing all four you cannot answer "is my caching
strategy working".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenUsage:
    """Full token usage breakdown from a Bedrock Converse response."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0

    @property
    def total_input_tokens(self) -> int:
        """All input tokens billed for this call (cached + uncached + write)."""
        return (
            self.input_tokens
            + self.cache_read_input_tokens
            + self.cache_write_input_tokens
        )

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.output_tokens

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of input tokens served from cache (0.0–1.0).

        Returns 0.0 when there are no input tokens.
        """
        denom = self.total_input_tokens
        if denom == 0:
            return 0.0
        return self.cache_read_input_tokens / denom

    def __add__(self, other: TokenUsage) -> TokenUsage:
        if not isinstance(other, TokenUsage):
            return NotImplemented
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
            cache_write_input_tokens=self.cache_write_input_tokens
            + other.cache_write_input_tokens,
        )


def parse_converse_usage(response: dict[str, Any]) -> TokenUsage:
    """Extract :class:`TokenUsage` from a ``converse()`` response.

    Tolerates missing fields: returns zeros for any field not in the
    response (older models, providers without prompt caching).
    """
    usage = response.get("usage") or {}
    return TokenUsage(
        input_tokens=int(usage.get("inputTokens", 0) or 0),
        output_tokens=int(usage.get("outputTokens", 0) or 0),
        cache_read_input_tokens=int(usage.get("cacheReadInputTokens", 0) or 0),
        cache_write_input_tokens=int(usage.get("cacheWriteInputTokens", 0) or 0),
    )


def aggregate_stream_usage(events: Iterable[dict[str, Any]]) -> TokenUsage:
    """Sum per-chunk usage from a ``converse_stream()`` event sequence.

    Bedrock emits a ``metadata`` event at end-of-stream containing the full
    usage payload. Some streaming wrappers also emit incremental usage; this
    function sums all of them so partial-stream measurements also work.
    """
    total = TokenUsage()
    for event in events:
        meta = event.get("metadata") or {}
        usage = meta.get("usage") or {}
        if not usage:
            continue
        total = total + TokenUsage(
            input_tokens=int(usage.get("inputTokens", 0) or 0),
            output_tokens=int(usage.get("outputTokens", 0) or 0),
            cache_read_input_tokens=int(usage.get("cacheReadInputTokens", 0) or 0),
            cache_write_input_tokens=int(usage.get("cacheWriteInputTokens", 0) or 0),
        )
    return total
