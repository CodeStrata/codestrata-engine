"""Cloud synthesis identifiers (Phase 4.7.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

POLICY_DISABLED = "cloud.conclusion.synthesis-disabled"
POLICY_INSUFFICIENT = "cloud.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "cloud.conclusion.cloud-hygiene-landscape-identified"
POLICY_RULE_EXECUTION = "cloud.conclusion.rule-execution-summary"
POLICY_PLATFORM = "cloud.conclusion.cloud-platform-adoption-observed"
POLICY_MULTI_CLOUD = "cloud.conclusion.multi-cloud-presence-observed"
POLICY_CONTAINERS = "cloud.conclusion.containerization-observed"
POLICY_ORCHESTRATION = "cloud.conclusion.kubernetes-orchestration-observed"
POLICY_IAC = "cloud.conclusion.iac-maturity-observed"
POLICY_SERVERLESS = "cloud.conclusion.serverless-adoption-observed"
POLICY_MANAGED = "cloud.conclusion.managed-cloud-services-observed"
POLICY_DEPLOYMENT = "cloud.conclusion.cloud-deployment-automation-observed"
POLICY_COVERAGE = "cloud.conclusion.cloud-technology-coverage-observed"
POLICY_WITHOUT_PLATFORM = "cloud.conclusion.deployment-without-platform-observed"
POLICY_NO_FINDINGS = "cloud.conclusion.no-hygiene-findings-in-supported-scope"
POLICY_UNSUPPORTED_SCOPE = "cloud.conclusion.unsupported-cloud-analysis-scope"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"cloud-theme:{digest}"


def build_conclusion_id(
    *,
    policy_id: str,
    repository_id: str,
    supporting_ids: Sequence[str],
) -> str:
    policy = require_nonblank(policy_id, label="policy_id").strip().lower()
    repo = require_nonblank(repository_id, label="repository_id").strip().lower()
    support = tuple(sorted({item.strip() for item in supporting_ids if str(item).strip()}))
    payload = f"policy:{policy}\nrepo:{repo}\nsupport:{','.join(support)}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"cloud-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(sorted({item.strip() for item in conclusion_ids if str(item).strip()}))
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"cloud-recommendation:{digest}"
