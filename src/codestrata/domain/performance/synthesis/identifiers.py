"""Performance synthesis identifiers (Phase 4.9.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

POLICY_DISABLED = "performance.conclusion.synthesis-disabled"
POLICY_INSUFFICIENT = "performance.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "performance.conclusion.performance-hygiene-landscape-identified"
POLICY_RULE_EXECUTION = "performance.conclusion.rule-execution-summary"
POLICY_DATA_ACCESS = "performance.conclusion.data-access-foundations-observed"
POLICY_BLOCKING = "performance.conclusion.blocking-operations-observed"
POLICY_CACHING = "performance.conclusion.caching-foundations-observed"
POLICY_CONCURRENCY = "performance.conclusion.concurrency-and-asynchronous-processing-observed"
POLICY_RESOURCE = "performance.conclusion.resource-management-observed"
POLICY_FRONTEND = "performance.conclusion.frontend-performance-controls-observed"
POLICY_OBSERVABILITY = "performance.conclusion.performance-observability-and-profiling-observed"
POLICY_CONFIGURATION = "performance.conclusion.configuration-controls-observed"
POLICY_BROAD = "performance.conclusion.broad-performance-foundations-observed"
POLICY_LIMITED = "performance.conclusion.limited-supporting-controls-observed"
POLICY_NO_FINDINGS = "performance.conclusion.no-performance-findings-in-supported-scope"
POLICY_UNSUPPORTED_SCOPE = "performance.conclusion.unsupported-performance-analysis-scope"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"performance-theme:{digest}"


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
    return f"performance-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(sorted({item.strip() for item in conclusion_ids if str(item).strip()}))
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"performance-recommendation:{digest}"
