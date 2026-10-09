"""Finding identity excludes rendered messages and presentation templates."""

from __future__ import annotations

from codestrata.domain.contracts.rules import ResolvedRule
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.graph.validation import require_nonblank


def finding_fingerprint(
    resolved: ResolvedRule,
    *,
    subject: str,
    rendered_message: str | None = None,
) -> str:
    """Stable finding fingerprint. ``rendered_message`` is ignored by design."""

    del rendered_message
    return digest_canonical(
        {
            "enabled": resolved.enabled,
            "effective_severity": resolved.effective_severity.value,
            "parameters": resolved.parameters,
            "revision": resolved.revision,
            "rule_digest": resolved.rule_digest,
            "rule_id": resolved.rule_id,
            "selector_digest": resolved.selector_digest,
            "subject": require_nonblank(subject, label="finding subject"),
        }
    )


def effective_setting_digest_for(resolved: ResolvedRule) -> str:
    return digest_canonical(
        {
            "enabled": resolved.enabled,
            "exception_refs": list(resolved.exception_refs),
            "parameters": resolved.parameters,
            "policy_refs": list(resolved.policy_refs),
            "revision": resolved.revision,
            "rule_id": resolved.rule_id,
            "selector_digest": resolved.selector_digest,
            "severity": resolved.effective_severity.value,
        }
    )
