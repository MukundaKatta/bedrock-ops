# Security Policy

## Supported Versions

bedrock-ops is at v0.1.x. Security fixes will be issued for the current minor (0.1.x). Older minors will not receive backports.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report privately by emailing `mukunda.vjcs6@gmail.com` with the subject `[bedrock-ops security]`. Include:

- A description of the vulnerability and its impact.
- The version of bedrock-ops affected (`pip show bedrock-ops`).
- Reproduction steps or a minimal proof-of-concept.
- Any suggested mitigation, if you have one.

You can expect:

- An acknowledgment within 5 business days.
- A status update within 14 days.
- A coordinated disclosure window of at most 90 days from the acknowledgment, after which the issue may be publicly disclosed.

## Specific Risk Surfaces in bedrock-ops

bedrock-ops wraps boto3 and exposes some AWS-credential-adjacent surfaces. Areas where security reports are especially welcome:

- The Guardrails redaction path (`safe_log_response`, `BedrockGuardrailViolation`) — a bug here could leak PII the library is supposed to redact.
- Throttle-code normalization (`install_throttle_normalizer`) — a bug here could mask real errors or cause unbounded retries.
- Conversation-history repair (`repair_orphan_tool_uses`) — incorrect handling could surface tool_use ids cross-tenant.

We will not pay bug bounties at this time.
