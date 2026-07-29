"""Test synthesis identifiers (Phase 4.6.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

POLICY_DISABLED = "testing.conclusion.synthesis-disabled"
POLICY_INSUFFICIENT = "testing.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "testing.conclusion.testing-hygiene-landscape-identified"
POLICY_RULE_EXECUTION = "testing.conclusion.rule-execution-summary"
POLICY_DISABLED_SKIPPED = "testing.conclusion.disabled-or-skipped-tests-observed"
POLICY_DISCOVERY = "testing.conclusion.test-discovery-uncertainty-observed"
POLICY_FRAMEWORK = "testing.conclusion.framework-declaration-gap-observed"
POLICY_COVERAGE_CI = "testing.conclusion.coverage-without-ci-observed"
POLICY_NO_FINDINGS = "testing.conclusion.no-hygiene-findings-in-supported-scope"
POLICY_UNSUPPORTED_SCOPE = "testing.conclusion.unsupported-test-analysis-scope"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"test-theme:{digest}"


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
    return f"test-conclusion:{policy}:{digest}"


def build_recommendation_id(
    *,
    conclusion_ids: Sequence[str],
    action_key: str,
) -> str:
    conclusions = tuple(sorted({item.strip() for item in conclusion_ids if str(item).strip()}))
    action = require_nonblank(action_key, label="action_key").strip().lower()
    payload = f"conclusions:{','.join(conclusions)}\naction:{action}\nv:{SYNTHESIS_VERSION}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"test-recommendation:{digest}"
