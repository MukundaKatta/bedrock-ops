# Changelog

All notable changes to `bedrock-ops` are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Dependency-free standard-library `unittest` suite under `tests/stdlib/` that
  exercises the boto3-free core (token usage and cache-hit-rate math, the
  capability table and cross-region prefix resolution, the PII-safe guardrail
  helpers, and the typed-error hierarchy) without installing `boto3`,
  `botocore`, `pytest`, or the package itself. Run it with
  `python3 -m unittest discover -s tests/stdlib -t tests/stdlib`.
- `stdlib tests` GitHub Actions workflow running that suite on Python
  3.10–3.13, plus a `py_compile` step over all tracked Python files.

### Notes
- The pytest suite (mocked `boto3`, coverage-gated) remains the canonical test
  run; the stdlib suite is an additive, install-free smoke test.

## [0.1.0] — 2026-05-08

Initial release. Closes the highest-pain Bedrock production gaps surfaced from 22 verified GitHub issues across boto3, strands-agents, langchain-aws, pydantic-ai, litellm, llama_index, mem0, and instructor.

### Added
- `BedrockClient` — production wrapper around `boto3.client('bedrock-runtime')` with sensible defaults (5 retry attempts, adaptive mode, 10s connect timeout, 120s read timeout) and typed exception mapping.
- Case-insensitive throttle code normalization via `install_throttle_normalizer()` — fixes `throttlingException` (lowercase) not being retried (strands-agents#905).
- `TokenUsage` dataclass with `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_write_input_tokens`, plus `cache_hit_rate` and `total_tokens` properties (strands#529).
- `parse_converse_usage()` and `aggregate_stream_usage()` helpers.
- `capabilities(model_id)` returns a `ModelCapabilities` for Anthropic Claude (Sonnet 4 / Opus 4 / 3.7 / 3.5 / Haiku 3.5), Amazon Nova (Pro / Lite / Micro), Mistral Large, and Meta Llama 3.3 70B. Resolves cross-region inference profile ids (`us.`, `eu.`, `apac.`).
- `precheck_features()` validates feature compatibility before the call; catches incompatible combos (boto3#4626).
- `register_model()` to add new models without waiting for a release.
- `BedrockGuardrailViolation` exception that carries categories but never the violating content (litellm#12152).
- `check_guardrail_intervention()`, `assert_no_guardrail_violation()`, `safe_log_response()` for PII-safe Guardrail handling.
- `repair_orphan_tool_uses()` for fixing conversation history after `guardrail_redact_input=True` strips tool_results (strands#1077).
- Typed error hierarchy: `BedrockOpsError`, `BedrockThrottled`, `BedrockTimeout`, `BedrockGuardrailViolation`, `BedrockValidationError`, `CapabilityUnknown`.

### Notes
- 49 unit tests, 90% line coverage.
- Lazy `boto3` import inside `BedrockClient.__init__` keeps top-level package import cheap (avoids the 290 MB import-time RAM regressions seen in instructor#2205 / opik#4633).
