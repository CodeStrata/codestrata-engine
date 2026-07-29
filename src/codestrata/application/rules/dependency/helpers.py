"""Shared helpers for Dependency hygiene SharedRules (Phase 4.4.3)."""

from __future__ import annotations

import re

from codestrata.application.rules.dependency.recommendations import recommendation_for
from codestrata.domain.dependency.ids import PACK_ID, PACK_VERSION, RULE_VERSION
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.models import (
    AggregatedDependencyEvidence,
    DependencyDeclarationEvidence,
    DependencyManifestEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch

# Mutable version syntax (bounded, documented). Ranges like >=1,<2 are NOT mutable.
_MUTABLE_TOKENS = frozenset(
    {
        "latest",
        "latest.release",
        "release",
        "+",
    }
)
_PLUS_WILDCARD_RE = re.compile(r"^\d+(\.\d+)*\.\+$")
_EXACT_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_RANGE_HINTS = ("<", ">", "=", "~", "^", "*", ",", "[", "]", "(", ")")
_URL_OR_VCS_HINTS = ("://", "git+", "hg+", "svn+", "bzr+")


def dependency_evidence(
    context: RuleExecutionContext,
) -> AggregatedDependencyEvidence | None:
    raw = context.dependency_evidence
    if isinstance(raw, AggregatedDependencyEvidence):
        return raw
    return None


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    remediation: str,
    severity: RuleSeverity = RuleSeverity.MEDIUM,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.DEPENDENCY,
        default_severity=severity,
        supported_languages=("java", "python", "php", "csharp"),
        tags=(
            "dependency",
            PACK_ID,
            "hygiene",
            "dimension:dependency",
        ),
        remediation_summary=remediation,
        documentation_reference=(
            "docs/analysis-intelligence/shared-rule-platform.md"
        ),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    remediation: str | None = None,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=remediation or recommendation_for(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_declaration(
    *,
    item: DependencyDeclarationEvidence,
    message: str,
    extra_attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    attributes = {
        "evidence_id": item.evidence_id,
        "ecosystem": item.ecosystem.value,
        "manifest_type": item.manifest_type.value,
        "declaration_kind": item.declaration_kind.value,
        "normalized_identity": item.normalized_identity,
        "original_identity": item.original_identity,
        "raw_version": item.raw_version or "",
        "resolved_version_local": item.resolved_version_local or "",
        "version_availability": item.version_availability.value,
        "version_resolution_status": item.version_resolution_status.value,
        "classification": item.classification.value,
        "configuration_name": item.configuration_name or "",
        "profile": item.profile or "",
        "group_name": item.group_name or "",
        "environment_marker": item.environment_marker or "",
        "optional": str(item.optional).lower(),
        "is_dependency_management": str(item.is_dependency_management).lower(),
        "extras": ",".join(item.extras),
    }
    if extra_attributes:
        attributes.update(extra_attributes)
    return RuleEvidence(
        kind=RuleEvidenceKind.DEPENDENCY,
        subject_reference=item.evidence_id,
        message=message,
        safe_location=item.source.path,
        line_start=item.source.line_start,
        line_end=item.source.line_end,
        attributes=attributes,
        provenance="aggregated_dependency_evidence",
    )


def evidence_manifest_expression(
    *,
    manifest: DependencyManifestEvidence,
    expression: str,
    message: str,
) -> RuleEvidence:
    return RuleEvidence(
        kind=RuleEvidenceKind.DEPENDENCY,
        subject_reference=manifest.evidence_id,
        message=message,
        safe_location=manifest.path,
        attributes={
            "evidence_id": manifest.evidence_id,
            "manifest_path": manifest.path,
            "ecosystem": manifest.ecosystem.value,
            "unresolved_expression": expression,
            "classification": manifest.classification.value,
        },
        provenance="aggregated_dependency_evidence",
    )


def version_text(item: DependencyDeclarationEvidence) -> str:
    return (item.resolved_version_local or item.raw_version or "").strip()


def is_local_or_direct_reference(item: DependencyDeclarationEvidence) -> bool:
    if item.is_local_path or item.is_editable:
        return True
    identity = (item.original_identity or item.normalized_identity or "").lower()
    raw = (item.raw_version or "").lower()
    snippet = (item.source.snippet or "").lower()
    combined = f"{identity} {raw} {snippet}"
    if any(hint in combined for hint in _URL_OR_VCS_HINTS):
        return True
    if identity.startswith((".", "/", "file:")):
        return True
    return False


def has_proven_unresolved_version(item: DependencyDeclarationEvidence) -> bool:
    """True only when evidence marks the expression as proven unresolved.

    Collector coverage gaps (unsupported Gradle interpolation, unfetched Maven
    parent/BOM, etc.) must not be treated as proven absence.
    """

    if is_local_or_direct_reference(item):
        return False
    if (
        item.version_resolution_status
        is DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
    ):
        return bool((item.raw_version or "").strip())
    # Legacy/partial payloads without version_resolution_status semantics:
    # never infer proven absence from generic UNAVAILABLE alone.
    return False


def has_unresolved_version_expression(item: DependencyDeclarationEvidence) -> bool:
    """Backward-compatible alias for proven unresolved detection."""

    return has_proven_unresolved_version(item)


def is_versionless_managed(
    item: DependencyDeclarationEvidence,
    *,
    managed_identities: frozenset[str],
) -> bool:
    if item.raw_version:
        return False
    if item.is_dependency_management:
        return True
    if item.ecosystem not in {DependencyEcosystem.MAVEN, DependencyEcosystem.GRADLE}:
        return False
    return item.normalized_identity in managed_identities


def managed_identities_for_manifest(
    declarations: tuple[DependencyDeclarationEvidence, ...],
    *,
    path: str,
) -> frozenset[str]:
    return frozenset(
        item.normalized_identity
        for item in declarations
        if item.source.path == path
        and (
            item.is_dependency_management
            or item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT
        )
    )


def is_mutable_version(version: str | None) -> bool:
    text = (version or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered in _MUTABLE_TOKENS:
        return True
    # Composer floating development branches.
    if lowered.startswith("dev-"):
        return True
    if _PLUS_WILDCARD_RE.match(text):
        return True
    if text.endswith("+") and not any(op in text for op in ("<", ">", "=")):
        # Bare trailing + (e.g. 1.2.+) already covered; lone '+' is mutable.
        if text == "+":
            return True
    if "-SNAPSHOT" in text.upper() or text.upper().endswith("SNAPSHOT"):
        # Require SNAPSHOT token rather than substring noise.
        if re.search(r"(?i)(^|[.-])SNAPSHOT$", text) or re.search(
            r"(?i)-SNAPSHOT($|[^A-Za-z0-9])", text
        ):
            return True
        if text.upper().endswith("-SNAPSHOT"):
            return True
    return False


def is_exact_version(version: str | None) -> bool:
    text = (version or "").strip()
    if not text:
        return False
    if any(hint in text for hint in _RANGE_HINTS):
        return False
    if is_mutable_version(text) and text.lower() in _MUTABLE_TOKENS:
        return False
    if _PLUS_WILDCARD_RE.match(text) or text == "+":
        return False
    return bool(_EXACT_VERSION_RE.match(text))


def overlap_context_key(item: DependencyDeclarationEvidence) -> tuple[str, ...]:
    """Narrow same-manifest overlap contract for conflict/duplicate grouping."""

    return (
        item.ecosystem.value,
        item.source.path,
        item.declaration_kind.value,
        item.configuration_name or "",
        item.profile or "",
        item.group_name or "",
        item.environment_marker or "",
        item.classification.value,
        str(item.is_dependency_management).lower(),
        str(item.optional).lower(),
    )


def duplicate_equivalence_key(item: DependencyDeclarationEvidence) -> tuple[str, ...]:
    return (
        *overlap_context_key(item),
        item.normalized_identity,
        version_text(item),
        ",".join(item.extras),
    )


def conflict_group_key(item: DependencyDeclarationEvidence) -> tuple[str, ...]:
    return (
        *overlap_context_key(item),
        item.normalized_identity,
    )


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    return {
        "taxonomy_id": "dependency.unknown",
        "assessment_dimensions": "dependency",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "recommendation_effort_band": "unknown",
        "recommendation_validation": "static_evidence_only",
        "recommendation_rationale": recommendation_for(rule_id),
        "recommendation_expected_outcome": (
            "Improve dependency declaration hygiene using repository-local facts"
        ),
    }
