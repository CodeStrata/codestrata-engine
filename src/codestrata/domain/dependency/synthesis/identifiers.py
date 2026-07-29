"""Dependency synthesis identifiers and transparent thresholds (Phase 4.4.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank

SYNTHESIS_VERSION = "1.0.0"

# Transparent concentration thresholds (proportions, not scores).
MANIFEST_FINDING_CONCENTRATION_MIN_SHARE = 0.40
PLUGIN_SHARE_MIN_FOR_THEME = 0.10

POLICY_DISABLED = "dependency.conclusion.disabled"
POLICY_INSUFFICIENT = "dependency.conclusion.insufficient-evidence"
POLICY_LANDSCAPE = "dependency.conclusion.dependency-landscape-identified"
POLICY_NO_PRODUCTION = "dependency.conclusion.no-production-hygiene-findings"
POLICY_PRODUCTION_PRESENT = "dependency.conclusion.production-hygiene-findings-present"
POLICY_TEST_FIXTURE = "dependency.conclusion.test-fixture-findings-present"
POLICY_MUTABLE = "dependency.conclusion.mutable-versions-present"
POLICY_UNBOUNDED = "dependency.conclusion.unbounded-requirements-present"
POLICY_DUPLICATE = "dependency.conclusion.duplicate-declarations-present"
POLICY_CONFLICTING = "dependency.conclusion.conflicting-exact-versions-present"
POLICY_UNRESOLVED = "dependency.conclusion.unresolved-versions-present"
POLICY_UNSUPPORTED_RESOLUTION = "dependency.conclusion.unsupported-resolution-coverage"
POLICY_PRODUCTION_PARTIAL = "dependency.conclusion.production-collection-partial"
POLICY_DECLARED_ONLY = "dependency.conclusion.declared-dependencies-only"
POLICY_UNSUPPORTED_ECOSYSTEM = "dependency.conclusion.unsupported-ecosystem-coverage"


def build_theme_id(*, kind: str, scope: str, subject: str = "") -> str:
    payload = f"{kind.strip().lower()}|{scope.strip().lower()}|{subject.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"dep-theme:{digest}"


def build_concentration_fact_id(*, kind: str, subject: str) -> str:
    payload = f"{kind}|{subject}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"dep-concentration:{digest}"


def build_conclusion_id(
    *,
    policy_id: str,
    repository_id: str,
    supporting_ids: Sequence[str],
) -> str:
    policy = require_nonblank(policy_id, label="policy_id").strip().lower()
    repo = require_nonblank(repository_id, label="repository_id").strip().lower()
    support = tuple(sorted({item.strip() for item in supporting_ids if str(item).strip()}))
    payload = (
        f"policy:{policy}\nrepo:{repo}\nsupport:{','.join(support)}\nv:{SYNTHESIS_VERSION}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"dep-conclusion:{policy}:{digest}"


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
    return f"dep-recommendation:{digest}"
