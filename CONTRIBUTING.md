# Contributing to bedrock-ops

bedrock-ops is a focused production toolkit for AWS Bedrock. Contributions are welcome where they fit that scope; out-of-scope contributions will be politely declined.

## In scope

- Bug fixes against the current Bedrock Runtime / Agent Runtime surface area.
- Better handling of botocore quirks that already appear in the code (case-insensitive throttle codes, `EventStreamError`, per-model timeouts).
- New entries in the capability lookup table when AWS releases a new Bedrock model.
- Additional Guardrail policy categories that surface in `safe_log_response`.
- Test coverage improvements (current target: 90%+ line coverage).
- Documentation fixes.

## Out of scope

- Agent frameworks, prompt managers, vector stores, RAG retrieval logic. Those have homes elsewhere.
- LLM routing across providers. bedrock-ops is Bedrock-only by design.
- Cosmetic changes that don't carry a tested behavioral improvement.

## Development setup

```bash
git clone https://github.com/MukundaKatta/bedrock-ops.git
cd bedrock-ops
uv sync --group dev
uv run pytest                              # 49 tests, ~90% coverage
uv run pytest --cov=bedrock_ops --cov-report=term-missing
uv build                                   # build sdist + wheel
```

Python 3.10+ required.

## Workflow

1. Open an issue first for anything bigger than a one-file change. This avoids spending hours on something that turns out to be out-of-scope.
2. Branch from `main`.
3. Write tests before or alongside the change (no untested behavior changes).
4. Run `uv run pytest` and confirm full suite still passes.
5. Open a PR against `main`. Fill in the template. Link the issue.
6. CI must be green before review.

## Coding conventions

- Type hints required on public APIs. Private helpers may use them at your discretion.
- No `Any` returns from public APIs unless the upstream API genuinely returns `dict[str, Any]` (e.g. raw boto3 responses).
- Prefer narrow, named exceptions over re-raising raw `botocore.exceptions.*`.
- Keep public symbols in `__all__`; otherwise they aren't re-exported.

## Release cadence

Releases follow semver. Patches: bug fixes only. Minor versions: new capability entries, new public symbols. Major versions: breaking changes (unlikely in v0.x).

Releases are cut by the maintainer via tag push. See `.github/workflows/release.yml`.
