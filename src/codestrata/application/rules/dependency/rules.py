"""Dependency declaration hygiene SharedRules (Phase 4.4.3).

Rules consume AggregatedDependencyEvidence only. They never re-parse manifests,
invoke build tools, or contact registries.
"""

from __future__ import annotations

from collections import defaultdict

from codestrata.application.rules.dependency.helpers import (
    conflict_group_key,
    dependency_evidence,
    duplicate_equivalence_key,
    evidence_declaration,
    has_proven_unresolved_version,
    is_exact_version,
    is_local_or_direct_reference,
    is_mutable_version,
    is_versionless_managed,
    make_metadata,
    managed_identities_for_manifest,
    match,
    version_text,
)
from codestrata.application.rules.dependency.yaml_rule import (
    render_template,
    yaml_metadata,
    yaml_title_and_template,
)
from codestrata.domain.dependency.ids import (
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyParseStatus,
)
from codestrata.domain.evidence.dependency.models import DependencyDeclarationEvidence
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleSkipReason
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult


def _dependency_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = dependency_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Dependency evidence unavailable",
        )
    if evidence.status in {
        DependencyParseStatus.NOT_APPLICABLE,
        DependencyParseStatus.INSUFFICIENT_EVIDENCE,
        DependencyParseStatus.SKIPPED,
    }:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=f"Dependency evidence status is {evidence.status.value}",
        )
    if not evidence.declarations and not evidence.manifests:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Dependency evidence contains no manifests or declarations",
        )
    return RuleApplicability.applicable()


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.subject_keys,
                    str(item.rule_id),
                    item.summary,
                ),
            )
        )
    )


class UnresolvedVersionRule:
    """Flags version expressions proven unresolved under a supported local contract."""

    @property
    def metadata(self) -> RuleMetadata:
        return yaml_metadata(
            RULE_UNRESOLVED_VERSION,
            make_metadata=make_metadata,
            remediation=(
                "Define or replace the unresolved local version expression with a "
                "concrete, locally resolvable value."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _dependency_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = dependency_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Dependency evidence unavailable",
            )
        matches: list[RuleMatch] = []
        seen_subjects: set[tuple[str, ...]] = set()
        for item in evidence.declarations:
            managed = managed_identities_for_manifest(evidence.declarations, path=item.source.path)
            if is_versionless_managed(item, managed_identities=managed):
                continue
            if not has_proven_unresolved_version(item):
                continue
            expression = item.raw_version or ""
            title, template, severity = yaml_title_and_template(RULE_UNRESOLVED_VERSION)
            subject_keys: tuple[str, ...] = (
                RULE_UNRESOLVED_VERSION,
                item.normalized_identity,
                item.source.path,
                expression,
                item.evidence_id,
            )
            if subject_keys in seen_subjects:
                continue
            seen_subjects.add(subject_keys)
            matches.append(
                match(
                    rule_id=RULE_UNRESOLVED_VERSION,
                    title=title,
                    summary=render_template(
                        template,
                        {
                            "identity": item.normalized_identity,
                            "path": item.source.path,
                            "expression": expression,
                        },
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_declaration(
                            item=item,
                            message=(
                                f"Version expression '{expression}' is proven "
                                "unresolved after inspecting supported local "
                                "manifest properties."
                            ),
                            extra_attributes={
                                "unresolved_expression": expression,
                                "version_resolution_status": (item.version_resolution_status.value),
                            },
                        ),
                    ),
                    subject_keys=subject_keys,
                )
            )
        return _sorted_matches(matches)


class MutableVersionRule:
    """Flags bounded mutable version syntax (SNAPSHOT, latest, +, 1.+, …)."""

    @property
    def metadata(self) -> RuleMetadata:
        return yaml_metadata(
            RULE_MUTABLE_VERSION,
            make_metadata=make_metadata,
            remediation=("Replace the mutable version expression with an exact pinned version."),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _dependency_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = dependency_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Dependency evidence unavailable",
            )
        matches = []
        for item in evidence.declarations:
            if is_local_or_direct_reference(item):
                continue
            raw = (item.raw_version or "").strip()
            resolved = (item.resolved_version_local or "").strip()
            candidate = resolved or raw
            if not is_mutable_version(candidate) and not is_mutable_version(raw):
                continue
            expression = raw or candidate
            title, template, severity = yaml_title_and_template(RULE_MUTABLE_VERSION)
            subject_keys = (
                RULE_MUTABLE_VERSION,
                item.normalized_identity,
                item.source.path,
                expression,
                item.evidence_id,
            )
            matches.append(
                match(
                    rule_id=RULE_MUTABLE_VERSION,
                    title=title,
                    summary=render_template(
                        template,
                        {
                            "identity": item.normalized_identity,
                            "path": item.source.path,
                            "expression": expression,
                        },
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_declaration(
                            item=item,
                            message=(
                                f"Mutable version expression '{expression}' may "
                                "resolve to different artifacts over time."
                            ),
                            extra_attributes={"mutable_expression": expression},
                        ),
                    ),
                    subject_keys=subject_keys,
                )
            )
        return _sorted_matches(matches)


class UnboundedRequirementRule:
    """Flags registry-style declarations with no effective version constraint."""

    @property
    def metadata(self) -> RuleMetadata:
        return yaml_metadata(
            RULE_UNBOUNDED_REQUIREMENT,
            make_metadata=make_metadata,
            remediation=(
                "Add an explicit version specifier so the selected version is "
                "constrained by the manifest."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _dependency_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = dependency_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Dependency evidence unavailable",
            )
        matches = []
        for item in evidence.declarations:
            if item.ecosystem is DependencyEcosystem.PYTHON:
                if is_local_or_direct_reference(item):
                    continue
                if item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT:
                    continue
                if version_text(item):
                    continue
                ecosystem_label = "Python package"
                reason = (
                    "Declaration has no version specifier; the selected version "
                    "is unconstrained by this manifest entry."
                )
            elif item.ecosystem is DependencyEcosystem.COMPOSER:
                if is_local_or_direct_reference(item):
                    continue
                raw = (version_text(item) or "").strip()
                if raw and raw != "*":
                    continue
                ecosystem_label = "Composer package"
                reason = (
                    "Declaration uses an unbounded Composer constraint "
                    f"('{raw or '(empty)'}'); the selected version is "
                    "unconstrained by this manifest entry."
                )
            elif item.ecosystem is DependencyEcosystem.NUGET:
                if is_local_or_direct_reference(item):
                    continue
                if item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT:
                    continue
                raw = (version_text(item) or "").strip()
                if raw and raw != "*" and "*" not in raw:
                    continue
                ecosystem_label = "NuGet package"
                reason = (
                    "Declaration uses an unbounded NuGet constraint "
                    f"('{raw or '(empty)'}'); the selected version is "
                    "unconstrained by this manifest entry."
                )
            else:
                continue
            extras = ",".join(item.extras)
            marker = item.environment_marker or ""
            extras_note = f" extras=[{extras}]" if extras else ""
            marker_note = f" (marker: {marker})" if marker else ""
            title, template, severity = yaml_title_and_template(RULE_UNBOUNDED_REQUIREMENT)
            subject_keys = tuple(
                part
                for part in (
                    RULE_UNBOUNDED_REQUIREMENT,
                    item.normalized_identity,
                    item.source.path,
                    extras or "-",
                    marker or "-",
                    item.group_name or "-",
                    item.evidence_id,
                )
                if part
            )
            matches.append(
                match(
                    rule_id=RULE_UNBOUNDED_REQUIREMENT,
                    title=title,
                    summary=render_template(
                        template,
                        {
                            "ecosystem_label": ecosystem_label,
                            "identity": item.normalized_identity,
                            "extras_note": extras_note,
                            "path": item.source.path,
                            "marker_note": marker_note,
                        },
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        evidence_declaration(
                            item=item,
                            message=reason,
                        ),
                    ),
                    subject_keys=subject_keys,
                )
            )
        return _sorted_matches(matches)


class ConflictingExactVersionsRule:
    """Flags same-context exact version conflicts within one manifest."""

    @property
    def metadata(self) -> RuleMetadata:
        return yaml_metadata(
            RULE_CONFLICTING_EXACT_VERSIONS,
            make_metadata=make_metadata,
            remediation=("Align conflicting exact versions in the same resolution context."),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _dependency_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = dependency_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Dependency evidence unavailable",
            )
        groups: dict[tuple[str, ...], list[DependencyDeclarationEvidence]] = defaultdict(list)
        for item in evidence.declarations:
            if item.is_dependency_management:
                continue
            if item.declaration_kind is DependencyDeclarationKind.DEPENDENCY_MANAGEMENT:
                continue
            if is_local_or_direct_reference(item):
                continue
            ver = version_text(item)
            if not is_exact_version(ver):
                continue
            groups[conflict_group_key(item)].append(item)

        matches: list[RuleMatch] = []
        for _key, items in sorted(groups.items(), key=lambda pair: pair[0]):
            versions = sorted({version_text(item) for item in items})
            if len(versions) < 2:
                continue
            ordered = sorted(
                items,
                key=lambda item: (
                    item.source.path,
                    item.evidence_id,
                    version_text(item),
                ),
            )
            evidence_ids = tuple(item.evidence_id for item in ordered)
            identity = ordered[0].normalized_identity
            subject_keys = (
                RULE_CONFLICTING_EXACT_VERSIONS,
                identity,
                ordered[0].source.path,
                *versions,
                *evidence_ids,
            )
            version_list = ", ".join(versions)
            locations = ", ".join(
                f"{item.source.path}:{item.source.line_start or '?'}" for item in ordered
            )
            title, template, severity = yaml_title_and_template(RULE_CONFLICTING_EXACT_VERSIONS)
            matches.append(
                match(
                    rule_id=RULE_CONFLICTING_EXACT_VERSIONS,
                    title=title,
                    summary=render_template(
                        template,
                        {
                            "identity": identity,
                            "version_list": version_list,
                            "locations": locations,
                        },
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=tuple(
                        evidence_declaration(
                            item=item,
                            message=(
                                f"Exact version '{version_text(item)}' participates "
                                "in a same-context conflict."
                            ),
                            extra_attributes={
                                "conflict_versions": version_list,
                                "participating_evidence_ids": ",".join(evidence_ids),
                            },
                        )
                        for item in ordered
                    ),
                    subject_keys=subject_keys,
                )
            )
        return _sorted_matches(matches)


class DuplicateDeclarationRule:
    """Flags equivalent repeated declarations in the same context."""

    @property
    def metadata(self) -> RuleMetadata:
        return yaml_metadata(
            RULE_DUPLICATE_DECLARATION,
            make_metadata=make_metadata,
            remediation=("Remove or consolidate the redundant equivalent declaration."),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _dependency_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = dependency_evidence(context)
        if evidence is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Dependency evidence unavailable",
            )
        groups: dict[tuple[str, ...], list[DependencyDeclarationEvidence]] = defaultdict(list)
        for item in evidence.declarations:
            groups[duplicate_equivalence_key(item)].append(item)

        matches: list[RuleMatch] = []
        for _key, items in sorted(groups.items(), key=lambda pair: pair[0]):
            if len(items) < 2:
                continue
            ordered = sorted(
                items,
                key=lambda item: (item.source.path, item.evidence_id),
            )
            evidence_ids = tuple(item.evidence_id for item in ordered)
            identity = ordered[0].normalized_identity
            version = version_text(ordered[0]) or "(none)"
            title, template, severity = yaml_title_and_template(RULE_DUPLICATE_DECLARATION)
            subject_keys: tuple[str, ...] = (
                RULE_DUPLICATE_DECLARATION,
                identity,
                ordered[0].source.path,
                version,
                *evidence_ids,
            )
            matches.append(
                match(
                    rule_id=RULE_DUPLICATE_DECLARATION,
                    title=title,
                    summary=render_template(
                        template,
                        {
                            "identity": identity,
                            "version": version,
                            "count": str(len(ordered)),
                            "path": ordered[0].source.path,
                        },
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=tuple(
                        evidence_declaration(
                            item=item,
                            message=(
                                "Equivalent declaration participates in a "
                                "same-context duplicate group."
                            ),
                            extra_attributes={
                                "duplicate_count": str(len(ordered)),
                                "participating_evidence_ids": ",".join(evidence_ids),
                            },
                        )
                        for item in ordered
                    ),
                    subject_keys=subject_keys,
                )
            )
        return _sorted_matches(matches)
