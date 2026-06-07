"""Dependency-free loader for the boto3-free parts of ``bedrock_ops``.

The standard-library ``unittest`` suite in this directory is designed to run
in a minimal environment that does **not** have ``boto3`` / ``botocore``
installed (e.g. ``python3 -m unittest discover -s tests/stdlib``). Importing
the top-level ``bedrock_ops`` package eagerly pulls in ``bedrock_ops._client``
and ``bedrock_ops._retry``, both of which import ``botocore`` at module import
time. That would make these tests impossible to run without the cloud SDK.

Most of the library, however, is pure Python with no AWS dependency:

* ``bedrock_ops._errors``           — the exception hierarchy
* ``bedrock_ops._capability_data``  — the static model table
* ``bedrock_ops._capabilities``     — capability lookup / precheck
* ``bedrock_ops._usage``            — token accounting
* ``bedrock_ops._guardrails``       — PII-safe guardrail helpers

This helper registers a lightweight namespace package for ``bedrock_ops`` and
loads only those pure submodules into ``sys.modules`` (under their real dotted
names, so ``@dataclass`` resolution works). It deliberately never executes the
package ``__init__`` and never touches ``_client`` / ``_retry``'s botocore
imports.

If ``botocore`` *is* available the same modules still load correctly, so this
file is safe to run in CI both with and without the SDK present.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

# tests/stdlib/_bootstrap.py -> repo root is two parents up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKG_DIR = _REPO_ROOT / "src" / "bedrock_ops"

# Pure, boto3-free submodules in dependency order (later entries may import
# earlier ones).
_PURE_MODULES = (
    "_errors",
    "_capability_data",
    "_capabilities",
    "_usage",
    "_guardrails",
)

_loaded = False


def _ensure_namespace_package() -> None:
    """Register a botocore-free ``bedrock_ops`` namespace package."""
    existing = sys.modules.get("bedrock_ops")
    if existing is not None and getattr(existing, "__path__", None):
        return
    pkg = types.ModuleType("bedrock_ops")
    pkg.__path__ = [str(_PKG_DIR)]  # type: ignore[attr-defined]
    sys.modules["bedrock_ops"] = pkg


def _load_submodule(name: str) -> types.ModuleType:
    full_name = f"bedrock_ops.{name}"
    cached = sys.modules.get(full_name)
    if cached is not None:
        return cached
    path = _PKG_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not build import spec for {full_name}")
    module = importlib.util.module_from_spec(spec)
    # Register *before* exec so @dataclass and intra-package imports resolve.
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_pure_modules() -> dict[str, Any]:
    """Load all boto3-free submodules and return a flat name -> object map."""
    global _loaded
    _ensure_namespace_package()
    for name in _PURE_MODULES:
        _load_submodule(name)
    _loaded = True

    from bedrock_ops import (  # noqa: PLC0415  (intentional late import)
        _capabilities,
        _capability_data,
        _errors,
        _guardrails,
        _usage,
    )

    return {
        # _errors
        "BedrockOpsError": _errors.BedrockOpsError,
        "BedrockThrottled": _errors.BedrockThrottled,
        "BedrockTimeout": _errors.BedrockTimeout,
        "BedrockGuardrailViolation": _errors.BedrockGuardrailViolation,
        "BedrockValidationError": _errors.BedrockValidationError,
        "CapabilityUnknown": _errors.CapabilityUnknown,
        # _capability_data
        "ModelCapabilities": _capability_data.ModelCapabilities,
        "_TABLE": _capability_data._TABLE,
        "_strip_cross_region_prefix": _capability_data._strip_cross_region_prefix,
        # _capabilities
        "capabilities": _capabilities.capabilities,
        "register_model": _capabilities.register_model,
        "precheck_features": _capabilities.precheck_features,
        # _usage
        "TokenUsage": _usage.TokenUsage,
        "parse_converse_usage": _usage.parse_converse_usage,
        "aggregate_stream_usage": _usage.aggregate_stream_usage,
        # _guardrails
        "GuardrailIntervention": _guardrails.GuardrailIntervention,
        "REDACTED": _guardrails.REDACTED,
        "check_guardrail_intervention": _guardrails.check_guardrail_intervention,
        "assert_no_guardrail_violation": _guardrails.assert_no_guardrail_violation,
        "safe_log_response": _guardrails.safe_log_response,
        "repair_orphan_tool_uses": _guardrails.repair_orphan_tool_uses,
    }
