"""Canonical customer-safe descriptive text contract for assessment reports.

Distinguishes secret *values* from safe prose about secret *findings*.
Platform Engineering Intelligence ingestion validates the same customer-facing
fields; Engine serialization must satisfy that gate without weakening it.

Accepted forms for redacted placeholders (exact leaf / assignment RHS):
- ``[REDACTED]`` (canonical Engine marker)
- ``<redacted>``
- ``REDACTED`` / ``[REDACTED]`` variants recognized by Platform
- asterisk masks (``***``)

Unsafe material (must never appear in customer-facing descriptive fields):
- credential values, bearer tokens, API keys
- private-key bodies and PEM begin/end fences (including header-only markers)
- credential-bearing connection strings
- source snippets containing secrets
- secret-shaped high-entropy tokens

Safe concepts (descriptive prose, not credentials):
- hardcoded credential detected
- password placeholder / secret-like configuration
- credential rotation recommended
- value redacted / intentionally vulnerable demonstration
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from codestrata.security.redaction import REDACTED, redact_report_payload, redact_secrets

# Deterministic replacement when a field must be rewritten categorically
# (preferred for newly authored SEC002 evidence; redaction covers legacy text).
PRIVATE_KEY_FINDING_EVIDENCE = (
    "Sensitive private-key material signature detected; value redacted."
)
PRIVATE_KEY_FINDING_DESCRIPTION_TEMPLATE = (
    "Sensitive credential material was detected in repository configuration. "
    "The value is redacted."
)

CANONICAL_REDACTED_MARKERS: frozenset[str] = frozenset(
    {
        REDACTED,
        "[REDACTED]",
        "<redacted>",
        "REDACTED",
        "***",
    }
)


def sanitize_customer_text(text: str | None) -> str:
    """Apply Engine secret redaction to a customer-facing string."""

    return redact_secrets(text)


def ensure_customer_safe_report_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deep-copied report document safe for customer / EI ingestion.

    Preserves IDs, rule IDs, severities, and structural relationships. Only
    secret-shaped presentation text is rewritten (typically to ``[REDACTED]``).
    """

    return redact_report_payload(document)


__all__ = [
    "CANONICAL_REDACTED_MARKERS",
    "PRIVATE_KEY_FINDING_DESCRIPTION_TEMPLATE",
    "PRIVATE_KEY_FINDING_EVIDENCE",
    "REDACTED",
    "ensure_customer_safe_report_document",
    "sanitize_customer_text",
]
