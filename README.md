# bedrock-ops

Production-grade boto3 toolkit for AWS Bedrock. Closes the gaps every team rebuilds when running Bedrock in production.

```bash
pip install bedrock-ops
```

```python
from bedrock_ops import BedrockClient

client = BedrockClient(region_name="us-east-1")
resp = client.converse(
    modelId="anthropic.claude-sonnet-4-20250514-v1:0",
    messages=[{"role": "user", "content": [{"text": "hello"}]}],
)
print(resp.text)
print(f"cache hit rate: {resp.usage.cache_hit_rate:.1%}")
```

## What it fixes

| Gap | How `bedrock-ops` fixes it | Upstream issue |
|---|---|---|
| Lowercase `throttlingException` not retried by botocore (case-sensitive match) | Installs an `after-call` hook that normalizes throttle codes to `ThrottlingException` so retries fire | [strands-agents#905](https://github.com/strands-agents/sdk-python/issues/905) |
| boto3 default 60s read timeout truncates long Sonnet 4 calls | Defaults to 120s; configurable per `BedrockClient` | [mem0#3825](https://github.com/mem0ai/mem0/issues/3825) |
| `cacheReadInputTokens` / `cacheWriteInputTokens` dropped by wrappers; can't measure cache hit rate | `TokenUsage` carries all four fields plus `cache_hit_rate` property | [strands#529](https://github.com/strands-agents/sdk-python/issues/529) |
| `ReadTimeoutError` dumps full traceback instead of typed catchable error | Wraps in `BedrockTimeout(kind="read", elapsed_s=...)` | [boto3#4561](https://github.com/boto/boto3/issues/4561) |
| `EventStreamError` from streaming throttles leaks connections from the pool | Wraps and ensures connection release | [boto3#4543](https://github.com/boto/boto3/issues/4543) (closed-not-planned) |
| No programmatic Bedrock model `maxTokens` lookup | `capabilities("...")` returns a typed `ModelCapabilities` | [boto3#4206](https://github.com/boto/boto3/issues/4206) |
| Bedrock Guardrails leak the violating PII into logs because the response carries the matched content | `safe_log_response()` returns a redacted copy; `BedrockGuardrailViolation` carries categories but no content | [litellm#12152](https://github.com/BerriAI/litellm/issues/12152) |
| `guardrail_redact_input=True` orphans `tool_use` blocks; next turn fails validation | `repair_orphan_tool_uses()` drops the orphans, restoring valid history | [strands#1077](https://github.com/strands-agents/sdk-python/issues/1077) |

## Why not `langchain-aws` or `strands-agents`?

- **`langchain-aws`** is coupled to LangChain runnables. You adopt the chain abstraction whether you want it or not.
- **`strands-agents`** is an agent framework. You adopt the loop, tool definition, and orchestration model.
- **`bedrock-ops`** is a thin functional toolkit on top of `boto3.client('bedrock-runtime')`. No chains, no agents. Use it from a Lambda, a FastAPI handler, a Glue job, or inside any framework that already has its own opinions.

## Install

Requires Python 3.10+. Pulls `boto3>=1.35` (already in your AWS Python projects).

```bash
pip install bedrock-ops
# or
uv add bedrock-ops
```

## Usage

### Production client (case-insensitive throttle retry, typed errors, full usage)

```python
from bedrock_ops import (
    BedrockClient, BedrockThrottled, BedrockTimeout, BedrockValidationError,
)

client = BedrockClient(
    region_name="us-east-1",
    max_attempts=5,           # default 5
    retry_mode="adaptive",    # also: "standard", "legacy"
    connect_timeout=10.0,     # default 10s
    read_timeout=120.0,       # default 120s — bedrock long-context safe
)

try:
    resp = client.converse(
        modelId="anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": "summarize this..."}]}],
        system=[{"text": "you are concise"}],
        inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
    )
except BedrockThrottled as e:
    log.warning("throttled after %s attempts in %s", e.attempts, e.region)
except BedrockTimeout as e:
    log.warning("bedrock %s timeout after %.1fs", e.kind, e.elapsed_s)
except BedrockValidationError as e:
    log.error("invalid request to %s: %s", e.model_id, e)

# Full usage including cache fields
print(resp.usage.input_tokens, resp.usage.cache_read_input_tokens)
print(f"cache hit rate this call: {resp.usage.cache_hit_rate:.1%}")
print(f"latency: {resp.latency_ms} ms")

# Tool calls if any
for tu in resp.tool_uses:
    print(tu["name"], tu["input"])
```

### Streaming with cache-aware aggregation

```python
from bedrock_ops import aggregate_stream_usage

events = list(client.converse_stream(
    modelId="anthropic.claude-sonnet-4-20250514-v1:0",
    messages=[{"role": "user", "content": [{"text": "..."}]}],
))
for event in events:
    if "contentBlockDelta" in event:
        print(event["contentBlockDelta"]["delta"].get("text", ""), end="")

# Sum usage across all metadata events in the stream
usage = aggregate_stream_usage(events)
print(f"\ntotal: {usage.total_tokens} ({usage.cache_hit_rate:.1%} cached)")
```

### Capability lookup

```python
from bedrock_ops import capabilities, precheck_features

cap = capabilities("anthropic.claude-sonnet-4-20250514-v1:0")
cap.max_input_tokens          # 200_000
cap.max_output_tokens         # 64_000
cap.supports_prompt_cache     # True
cap.supports_thinking         # True
cap.available_regions         # ('us-east-1', 'us-east-2', 'us-west-2', ...)

# Cross-region inference profile ids resolve to the bare model:
capabilities("us.anthropic.claude-sonnet-4-20250514-v1:0")  # works

# Validate feature combos before the call (catches boto3#4626 silent ValidationException)
precheck_features(
    "anthropic.claude-sonnet-4-20250514-v1:0",
    use_prompt_cache=True,
    use_thinking=True,
    region="us-east-1",
)
```

For new model releases:

```python
from bedrock_ops import register_model, ModelCapabilities

register_model(ModelCapabilities(
    model_id="anthropic.claude-X-2026...",
    family="anthropic.claude",
    max_input_tokens=200_000,
    max_output_tokens=128_000,
    supports_vision=True,
    supports_tool_use=True,
    supports_prompt_cache=True,
    supports_thinking=True,
    supports_streaming=True,
    supports_cross_region_inference=True,
    available_regions=("us-east-1", "us-west-2"),
))
```

### Guardrails without PII leaks

```python
from bedrock_ops import (
    safe_log_response, assert_no_guardrail_violation, BedrockGuardrailViolation,
)

resp = client.converse(
    modelId="...",
    messages=[...],
    guardrailConfig={"guardrailIdentifier": "gid-123", "guardrailVersion": "DRAFT"},
)

# Option A: detect without raising
if resp.guardrail and resp.guardrail.action == "BLOCKED":
    log.info("guardrail fired", categories=resp.guardrail.categories)
    # resp.guardrail has NO content — safe to log

# Option B: raise on intervention
try:
    assert_no_guardrail_violation(resp.raw, guardrail_id="gid-123")
except BedrockGuardrailViolation as e:
    # str(e) and repr(e) contain no PII; only category names
    log.warning("blocked: categories=%s", e.categories)

# Always: redact before sending to a structured logger or trace store
logger.info("converse done", extra={"resp": safe_log_response(resp.raw, guardrail_id="gid-123")})
```

### Repairing conversation history after Guardrails redaction

```python
from bedrock_ops import repair_orphan_tool_uses

# After Guardrails has stripped some tool_results from history, calling
# converse() again would fail with a ValidationException because the
# orphaned tool_use blocks have no matching tool_result. Run this first:
clean_messages = repair_orphan_tool_uses(messages)
client.converse(modelId=..., messages=clean_messages, ...)
```

## What it explicitly does NOT do

- Not an agent framework.
- Not an LLM router. Bedrock-only by design.
- Not a vector DB or RAG framework.
- Not a prompt management UI.
- Not a tracer or observability platform. Compose with Phoenix / Langfuse / Datadog / OTel as you would with raw boto3.
- Not async-first in v0.1. Async support via `aioboto3` is planned for v0.2.

## Versioning

`bedrock-ops` follows semantic versioning. The capability table is treated as data, not API: new models added in patch releases. Breaking API changes get a major bump.

## Contributing

Issues and PRs welcome at <https://github.com/MukundaKatta/bedrock-ops>. The roadmap below indicates what's coming next; if you need something else, open an issue first to discuss scope.

## Roadmap

- v0.2: async-first via `aioboto3`; normalized streaming event taxonomy (`text_delta` / `tool_use_delta` / `thinking_delta` / `tool_result`).
- v0.3: per-call cost computation with versioned price tables.
- v0.4: pre-inference token counting via the Bedrock CountTokens API.
- v0.5: bedrock-agent-runtime support (invoke_agent + retrieve).

## License

Apache-2.0. See [LICENSE](./LICENSE).
