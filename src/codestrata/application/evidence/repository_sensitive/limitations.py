"""Standard limitations for repository-sensitive evidence."""

from __future__ import annotations

from codestrata.domain.evidence.repository_sensitive.enums import (
    RepositorySensitiveLimitationCategory,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import make_limitation_id
from codestrata.domain.evidence.repository_sensitive.models import (
    RepositorySensitiveLimitation,
)

_STANDARD: tuple[tuple[RepositorySensitiveLimitationCategory, str], ...] = (
    (
        RepositorySensitiveLimitationCategory.REPOSITORY_SNAPSHOT_ONLY,
        "Evidence reflects the current repository snapshot only.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_GIT_HISTORY,
        "Git history is not scanned for historical secrets or credential commits.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_RUNTIME_ENVIRONMENT,
        "Runtime environment variables and deployed secrets are not inspected.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_SECRET_VALIDITY_VERIFICATION,
        "Observed literals are not verified as active or valid secrets.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_ENTROPY_ANALYSIS,
        "Entropy-based secret detection is not performed.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_EXTERNAL_CREDENTIAL_VALIDATION,
        "External credential validation and live service checks are not performed.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_CERTIFICATE_TRUST_VALIDATION,
        "Certificate trust chains and expiry are not validated.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_KEYSTORE_DECRYPTION,
        "Keystore and PKCS#12 entries are not decrypted or enumerated.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_ARBITRARY_SOURCE_SCANNING,
        "Arbitrary source-code credential regex scanning is not performed.",
    ),
    (
        RepositorySensitiveLimitationCategory.NO_VULNERABILITY_INTERPRETATION,
        "No vulnerability, severity, compliance, or remediation interpretation is applied.",
    ),
)


def standard_limitations() -> tuple[RepositorySensitiveLimitation, ...]:
    return tuple(
        RepositorySensitiveLimitation(
            limitation_id=make_limitation_id(
                category=category.value, summary=summary
            ),
            category=category,
            summary=summary,
        )
        for category, summary in _STANDARD
    )
