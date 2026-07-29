"""AI Readiness synthesis identifiers (Phase 4.8.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

POLICY_DISABLED = "ai_readiness.conclusion.synthesis-disabled"
POLICY_INSUFFICIENT = "ai_readiness.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "ai_readiness.conclusion.ai-readiness-hygiene-landscape-identified"
POLICY_RULE_EXECUTION = "ai_readiness.conclusion.rule-execution-summary"
POLICY_API_BOUNDARIES = "ai_readiness.conclusion.api-and-service-boundaries-observed"
POLICY_DOCUMENTATION = "ai_readiness.conclusion.documentation-maturity-observed"
POLICY_DATA_RETRIEVAL = "ai_readiness.conclusion.data-and-retrieval-foundations-observed"
POLICY_AI_INTEGRATION = "ai_readiness.conclusion.ai-integration-maturity-observed"
POLICY_MCP_TOOLS = "ai_readiness.conclusion.mcp-and-tool-ecosystem-observed"
POLICY_WORKFLOW_AGENT = "ai_readiness.conclusion.workflow-and-agent-foundations-observed"
POLICY_OBSERVABILITY = "ai_readiness.conclusion.observability-and-governance-observed"
POLICY_BROAD = "ai_readiness.conclusion.broad-ai-enablement-observed"
POLICY_LIMITED = "ai_readiness.conclusion.limited-supporting-foundations-observed"
POLICY_NO_FINDINGS = "ai_readiness.conclusion.no-hygiene-findings-in-supported-scope"
POLICY_UNSUPPORTED_SCOPE = "ai_readiness.conclusion.unsupported-ai-readiness-analysis-scope"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"ai-readiness-theme:{digest}"


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
    return f"ai-readiness-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(sorted({item.strip() for item in conclusion_ids if str(item).strip()}))
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ai-readiness-recommendation:{digest}"
