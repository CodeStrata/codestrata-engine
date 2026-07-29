"""Map Shared Rule Platform matches onto existing Finding models."""

from __future__ import annotations

from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.rules.results import RuleMatch

_CATEGORY_MAP: dict[RuleCategory, FindingCategory] = {
    RuleCategory.ARCHITECTURE: FindingCategory.ARCHITECTURE,
    RuleCategory.TECHNICAL_DEBT: FindingCategory.TECHNICAL_DEBT,
    RuleCategory.DEPENDENCY: FindingCategory.DEPENDENCY,
    RuleCategory.SECURITY: FindingCategory.SECURITY,
    RuleCategory.TESTING: FindingCategory.TESTING,
    RuleCategory.CLOUD: FindingCategory.CLOUD,
    RuleCategory.AI_READINESS: FindingCategory.AI_READINESS,
    RuleCategory.PERFORMANCE: FindingCategory.PERFORMANCE,
    RuleCategory.PLATFORM: FindingCategory.GOVERNANCE,
    RuleCategory.EXPERIMENTAL: FindingCategory.UNKNOWN,
}


class RuleFindingMapper:
    """Map validated matches to Phase 3 Finding models without altering ID scheme."""

    def map_match(self, match: RuleMatch, *, category: RuleCategory) -> Finding:
        evidence = tuple(
            FindingEvidence(
                evidence_type=item.kind.value,
                source_id=item.subject_reference,
                path=item.safe_location,
                excerpt=item.message or None,
            )
            for item in match.evidence
        )
        subjects = list(match.subject_keys) or list(match.affected_entities)
        if not subjects:
            subjects = [item.subject_reference for item in match.evidence]
        metadata: dict[str, str] = {
            "rule_version": str(match.rule_version),
            "confidence": match.confidence.value,
            "remediation": match.remediation or "",
            "provenance": match.provenance,
            "shared_rule_platform": "true",
            "business_impact": "unknown",
            "subject_keys": ",".join(str(item) for item in subjects),
        }
        if match.provenance == "architecture.core" or str(match.rule_id).startswith(
            "architecture."
        ):
            from codestrata.application.rules.architecture.helpers import enrich_finding_metadata

            metadata.update(enrich_finding_metadata(str(match.rule_id)))
        elif match.provenance == "technical_debt.core" or str(match.rule_id).startswith(
            "technical_debt."
        ):
            from codestrata.application.rules.technical_debt.helpers import (
                enrich_finding_metadata as enrich_debt_metadata,
            )

            metadata.update(enrich_debt_metadata(str(match.rule_id)))
            metadata.update(_technical_debt_evidence_metadata(match))
        elif match.provenance == "dependency.core" or str(match.rule_id).startswith(
            "dependency."
        ):
            from codestrata.application.rules.dependency.helpers import (
                enrich_finding_metadata as enrich_dependency_metadata,
            )

            metadata.update(enrich_dependency_metadata(str(match.rule_id)))
            metadata.update(_dependency_evidence_metadata(match))
        elif match.provenance == "security.core" or str(match.rule_id).startswith(
            "security."
        ):
            from codestrata.application.rules.security.helpers import (
                enrich_finding_metadata as enrich_security_metadata,
            )

            metadata.update(enrich_security_metadata(str(match.rule_id)))
            metadata.update(_security_evidence_metadata(match))
        elif match.provenance == "testing.core" or str(match.rule_id).startswith(
            "testing."
        ):
            from codestrata.application.rules.testing.helpers import (
                enrich_finding_metadata as enrich_testing_metadata,
            )

            metadata.update(enrich_testing_metadata(str(match.rule_id)))
            metadata.update(_testing_evidence_metadata(match))
        elif match.provenance == "cloud.core" or str(match.rule_id).startswith(
            "cloud."
        ):
            from codestrata.application.rules.cloud.helpers import (
                enrich_finding_metadata as enrich_cloud_metadata,
            )

            metadata.update(enrich_cloud_metadata(str(match.rule_id)))
            metadata.update(_cloud_evidence_metadata(match))
        elif match.provenance == "ai_readiness.core" or str(match.rule_id).startswith(
            "ai_readiness."
        ):
            from codestrata.application.rules.ai_readiness.helpers import (
                enrich_finding_metadata as enrich_ai_readiness_metadata,
            )

            metadata.update(enrich_ai_readiness_metadata(str(match.rule_id)))
            metadata.update(_ai_readiness_evidence_metadata(match))
        elif match.provenance == "performance.core" or str(match.rule_id).startswith(
            "performance."
        ):
            from codestrata.application.rules.performance.helpers import (
                enrich_finding_metadata as enrich_performance_metadata,
            )

            metadata.update(enrich_performance_metadata(str(match.rule_id)))
            metadata.update(_performance_evidence_metadata(match))
        return Finding.create(
            rule_id=str(match.rule_id),
            title=match.title,
            description=match.summary,
            severity=_map_severity(match.severity),
            category=_CATEGORY_MAP.get(category, FindingCategory.UNKNOWN),
            evidence=evidence,
            metadata=metadata,
            subject_keys=tuple(subjects),
        )

    def map_matches(
        self,
        matches: tuple[RuleMatch, ...],
        *,
        category_by_rule: dict[str, RuleCategory],
    ) -> tuple[Finding, ...]:
        findings = [
            self.map_match(
                match,
                category=category_by_rule.get(str(match.rule_id), RuleCategory.PLATFORM),
            )
            for match in matches
        ]
        return tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))


def _map_severity(severity: FindingSeverity) -> FindingSeverity:
    # RuleSeverity is an alias of FindingSeverity.
    return severity


_TD_EVIDENCE_METADATA_KEYS = (
    "metric",
    "value",
    "threshold",
    "severity_basis",
    "classification",
    "language",
    "callable_kind",
    "type_kind",
    "evidence_id",
)


def _technical_debt_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match complexity attributes for reviewable Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _TD_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    if match.evidence[0].line_end is not None:
        promoted["line_end"] = str(match.evidence[0].line_end)
    return promoted


_DEP_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "ecosystem",
    "manifest_type",
    "declaration_kind",
    "normalized_identity",
    "original_identity",
    "raw_version",
    "resolved_version_local",
    "version_resolution_status",
    "classification",
    "configuration_name",
    "profile",
    "group_name",
    "environment_marker",
    "unresolved_expression",
    "mutable_expression",
    "conflict_versions",
    "participating_evidence_ids",
    "duplicate_count",
)


def _dependency_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match dependency attributes for reviewable Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _DEP_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    if match.evidence[0].line_end is not None:
        promoted["line_end"] = str(match.evidence[0].line_end)
    # Preserve all participating evidence IDs when multi-evidence matches.
    if len(match.evidence) > 1:
        ids = [
            item.attributes.get("evidence_id") or item.subject_reference
            for item in match.evidence
        ]
        promoted["participating_evidence_ids"] = ",".join(
            item for item in ids if item
        )
    return promoted


_SEC_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "path",
    "kind",
    "inspection_status",
    "content_classifications",
    "classification",
    "normalized_key",
    "key_family",
    "value_kind",
    "placeholder_status",
    "redacted_preview",
    "value_fingerprint",
    "section",
    "literal_boolean",
    "is_wildcard_origin",
    "security_category",
)


def _security_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match repository-sensitive attributes for Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _SEC_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    return promoted


_TEST_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "path",
    "marker_type",
    "marker_text",
    "marker_count",
    "marker_types",
    "hotspot_paths",
    "role",
    "confirmation_level",
    "language_hint",
    "framework",
    "basis",
    "declared_version",
    "detail",
    "fact_type",
    "tool",
    "job_or_step",
    "command_projection",
    "considered_count",
    "unconfirmed_count",
    "unconfirmed_ratio",
    "coverage_configurations",
    "ci_files_inspected",
    "testing_category",
)

_CLOUD_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "path",
    "confirmation_level",
    "detail",
    "platforms",
    "platform_count",
    "container_kinds",
    "orchestration_kinds",
    "iac_kinds",
    "iac_kind_count",
    "serverless_kinds",
    "deployment_systems",
    "managed_services",
    "managed_service_count",
    "families",
    "family_count",
    "technologies",
    "deployment_asset_kinds",
    "cloud_category",
)

_AI_READINESS_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "path",
    "confirmation_level",
    "detail",
    "api_boundary_kinds",
    "openapi_fact_count",
    "documentation_kinds",
    "supporting_documentation_kinds",
    "data_access_kinds",
    "search_retrieval_kinds",
    "vector_embedding_signals",
    "llm_kinds",
    "prompt_kinds",
    "rag_kinds",
    "tool_mcp_kinds",
    "workflow_agent_kinds",
    "observability_governance_kinds",
    "ai_related_assets",
    "families",
    "family_count",
    "technologies",
    "ai_readiness_category",
)

_PERFORMANCE_EVIDENCE_METADATA_KEYS = (
    "evidence_id",
    "path",
    "confirmation_level",
    "detail",
    "data_access_kinds",
    "data_access_kind_count",
    "data_access_control_kinds",
    "blocking_sleep_kinds",
    "sync_io_kinds",
    "caching_kinds",
    "concurrency_kinds",
    "executor_concurrency_kinds",
    "executor_config_kinds",
    "resource_kinds",
    "frontend_bundle_kinds",
    "frontend_lazy_kinds",
    "frontend_kinds",
    "observability_kinds",
    "configuration_kinds",
    "data_or_blocking",
    "performance_assets",
    "families",
    "family_count",
    "technologies",
    "performance_category",
)


def _testing_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match repository-testing attributes for Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _TEST_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    return promoted


def _cloud_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match repository-cloud attributes for Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _CLOUD_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    return promoted


def _ai_readiness_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match repository AI-readiness attributes for Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _AI_READINESS_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    return promoted


def _performance_evidence_metadata(match: RuleMatch) -> dict[str, str]:
    """Promote first-match repository performance attributes for Finding metadata."""

    if not match.evidence:
        return {}
    attrs = match.evidence[0].attributes
    promoted: dict[str, str] = {}
    for key in _PERFORMANCE_EVIDENCE_METADATA_KEYS:
        value = attrs.get(key)
        if value:
            promoted[key] = value
    if match.evidence[0].line_start is not None:
        promoted["line_start"] = str(match.evidence[0].line_start)
    return promoted


def explain_finding_identity(match: RuleMatch) -> dict[str, str]:
    subjects = list(match.subject_keys) or list(match.affected_entities)
    if not subjects:
        subjects = [item.subject_reference for item in match.evidence]
    if not subjects:
        subjects = ["repository"]
    return {
        "scheme": "finding:{rule_id}:{sha256(sorted_subjects)[:16]}",
        "rule_id": str(match.rule_id),
        "subjects": ",".join(sorted(set(subjects))),
        "note": "Uses existing build_finding_id; timestamps and execution order are ignored",
    }