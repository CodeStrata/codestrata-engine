"""Security synthesis identifiers (Phase 4.5.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

POLICY_DISABLED = "security.conclusion.synthesis-disabled"
POLICY_INSUFFICIENT = "security.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "security.conclusion.security-hygiene-landscape-identified"
POLICY_NO_PRODUCTION = "security.conclusion.no-production-findings-in-supported-scope"
POLICY_PRODUCTION_PRESENT = "security.conclusion.production-security-findings-present"
POLICY_TEST_FIXTURE = "security.conclusion.test-or-fixture-findings-only"
POLICY_UNKNOWN_ROLE = "security.conclusion.unknown-role-findings-present"
POLICY_PRIVATE_KEY = "security.conclusion.private-key-material-detected"
POLICY_LITERAL_CREDENTIAL = "security.conclusion.literal-credentials-detected"
POLICY_PLACEHOLDER = "security.conclusion.placeholder-credentials-detected"
POLICY_TRANSPORT = "security.conclusion.transport-verification-disabled"
POLICY_AUTHENTICATION = "security.conclusion.authentication-explicitly-disabled"
POLICY_CORS = "security.conclusion.permissive-cors-configured"
POLICY_DEBUG = "security.conclusion.debug-enabled"
POLICY_CONCENTRATION = "security.conclusion.findings-concentrated"
POLICY_PARTIAL_EVIDENCE = "security.conclusion.partial-evidence-coverage"
POLICY_UNSUPPORTED_SCOPE = "security.conclusion.unsupported-security-analysis-scope"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"sec-theme:{digest}"


def build_concentration_fact_id(*, kind: str, subject: str) -> str:
    payload = f"{kind}|{subject}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"sec-concentration:{digest}"


def build_conclusion_id(
    *,
    policy_id: str,
    repository_id: str,
    supporting_ids: Sequence[str],
) -> str:
    policy = require_nonblank(policy_id, label="policy_id").strip().lower()
    repo = require_nonblank(repository_id, label="repository_id").strip().lower()
    support = tuple(
        sorted({item.strip() for item in supporting_ids if str(item).strip()})
    )
    payload = (
        f"policy:{policy}\nrepo:{repo}\nsupport:{','.join(support)}\nv:{SYNTHESIS_VERSION}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"sec-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(
        sorted({item.strip() for item in conclusion_ids if str(item).strip()})
    )
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = (
        f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"sec-recommendation:{digest}"
