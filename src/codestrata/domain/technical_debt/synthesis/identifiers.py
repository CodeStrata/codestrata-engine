"""Technical Debt synthesis identifiers (Phase 4.3.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

# Transparent concentration thresholds (proportions, not scores).
PACKAGE_CONCENTRATION_MIN_SHARE = 0.15
HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE = 0.40

POLICY_COMPLEXITY_PRESENT = "technical_debt.conclusion.complexity-present"
POLICY_THEME_PREFIX = "technical_debt.conclusion.theme-"
POLICY_PACKAGE_CONCENTRATION = "technical_debt.conclusion.package-concentration"
POLICY_HOTSPOT_CONCENTRATION = "technical_debt.conclusion.hotspot-concentration"
POLICY_MULTI_RULE_HOTSPOTS = "technical_debt.conclusion.multi-rule-hotspots"
POLICY_NO_PRODUCTION = "technical_debt.conclusion.no-production-findings"
POLICY_PARTIAL_COVERAGE = "technical_debt.conclusion.partial-coverage"
POLICY_TEST_MAINTAINABILITY = "technical_debt.conclusion.test-maintainability"
POLICY_DISABLED = "technical_debt.conclusion.disabled"


def build_theme_id(*, taxonomy_id: str, rule_id: str, source_role: str) -> str:
    payload = f"{taxonomy_id}|{rule_id}|{source_role}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"td-theme:{digest}"


def build_concentration_fact_id(*, kind: str, subject: str) -> str:
    payload = f"{kind}|{subject}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"td-concentration:{digest}"


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
    return f"td-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(
        sorted({item.strip() for item in conclusion_ids if str(item).strip()})
    )
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"td-recommendation:{digest}"


def theme_policy_id(rule_id: str) -> str:
    leaf = rule_id.rsplit(".", 1)[-1]
    return f"{POLICY_THEME_PREFIX}{leaf}"
