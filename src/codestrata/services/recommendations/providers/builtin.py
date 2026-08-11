"""Builtin finding → recommendation providers."""

from __future__ import annotations

from codestrata.domain.findings import Finding, FindingEvidence
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationEvidence,
    RecommendationPriority,
)
from codestrata.services.recommendations.context import RecommendationContext
from codestrata.services.recommendations.priority import priority_from_finding_severity

_README = "codestrata-rule-missing-readme"
_LICENSE = "codestrata-rule-missing-license"
_TESTS = "codestrata-rule-missing-tests"
_CI = "codestrata-rule-missing-ci-workflow"
_MVNW = "codestrata-rule-maven-wrapper-missing"
_NPM_LOCK = "codestrata-rule-npm-lockfile-missing"
_BOOT_UNSUPPORTED = "codestrata-rule-unsupported-spring-boot-version"
_JAVA = "codestrata-rule-java-detected"
_NODE_ENGINE_MISSING = "codestrata-rule-missing-node-engine"
_LARGE = "codestrata-rule-large-repository"


def _actions(*steps: tuple[str, str, str | None, str | None]) -> tuple[RecommendationAction, ...]:
    return tuple(
        RecommendationAction(
            order=index,
            title=title,
            description=description,
            command=command,
            documentation_ref=doc,
        )
        for index, (title, description, command, doc) in enumerate(steps, start=1)
    )


def _evidence_from_finding(finding: Finding) -> tuple[RecommendationEvidence, ...]:
    items: list[RecommendationEvidence] = [
        RecommendationEvidence(
            evidence_type="finding",
            source_id=finding.id,
            excerpt=finding.title,
        )
    ]
    for item in finding.evidence:
        items.append(_map_finding_evidence(item))
    return tuple(items)


def _map_finding_evidence(item: FindingEvidence) -> RecommendationEvidence:
    return RecommendationEvidence(
        evidence_type=item.evidence_type,
        source_id=item.source_id,
        path=item.path,
        excerpt=item.excerpt,
        node_id=item.node_id,
    )


def _base(
    *,
    provider_id: str,
    finding: Finding,
    title: str,
    summary: str,
    rationale: str,
    category: RecommendationCategory,
    actions: tuple[RecommendationAction, ...],
    priority: RecommendationPriority | None = None,
    subject_keys: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
) -> Recommendation:
    from codestrata.application.traceability.recommendation import (
        select_primary_finding_id,
    )
    from codestrata.domain.recommendations.enums import RecommendationType
    from codestrata.domain.traceability import EvidenceCompleteness

    finding_ids = (finding.id,)
    return Recommendation.create(
        provider_id=provider_id,
        title=title,
        summary=summary,
        rationale=rationale,
        priority=priority or priority_from_finding_severity(finding.severity),
        category=category,
        related_finding_ids=finding_ids,
        supporting_finding_ids=finding_ids,
        primary_finding_id=select_primary_finding_id((finding,)) or finding.id,
        recommendation_type=RecommendationType.FINDING_BACKED,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=actions,
        evidence=_evidence_from_finding(finding),
        affected_node_ids=finding.affected_assessment_node_ids,
        subject_keys=subject_keys or (finding.id, provider_id),
        metadata={
            "source_finding_rule_id": finding.rule_id,
            **(metadata or {}),
        },
    )


class MissingReadmeRecommendation:
    def id(self) -> str:
        return "codestrata-rec-missing-readme"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_README})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Add a README",
                summary="Create a root README that documents purpose, setup, and usage.",
                rationale=finding.description,
                category=RecommendationCategory.DOCUMENTATION,
                actions=_actions(
                    (
                        "Draft README skeleton",
                        "Add project purpose, prerequisites, and how to run locally.",
                        None,
                        "https://docs.github.com/en/repositories/about-readmes",
                    ),
                    (
                        "Document build and test",
                        "Include commands to build, test, and package the project.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class MissingLicenseRecommendation:
    def id(self) -> str:
        return "codestrata-rec-missing-license"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_LICENSE})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Add an explicit LICENSE",
                summary="Choose and commit a license file so consumers know usage terms.",
                rationale=finding.description,
                category=RecommendationCategory.GOVERNANCE,
                actions=_actions(
                    (
                        "Select a license",
                        "Agree on an open-source or proprietary license with stakeholders.",
                        None,
                        "https://choosealicense.com/",
                    ),
                    (
                        "Add LICENSE file",
                        "Commit LICENSE (or LICENSE.md) at the repository root.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class MissingTestsRecommendation:
    def id(self) -> str:
        return "codestrata-rec-missing-tests"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_TESTS})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Establish a test baseline",
                summary="Introduce automated tests for critical paths and wire them into CI.",
                rationale=finding.description,
                category=RecommendationCategory.TESTING,
                actions=_actions(
                    (
                        "Establish test baseline",
                        "Create a minimal automated test suite that can run locally.",
                        None,
                        None,
                    ),
                    (
                        "Prioritize critical paths",
                        "Cover authentication, data mutations, and other high-risk flows first.",
                        None,
                        None,
                    ),
                    (
                        "Add test execution to CI",
                        "Fail the pipeline when tests fail so regressions are caught early.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class MissingCiRecommendation:
    def id(self) -> str:
        return "codestrata-rec-missing-ci-workflow"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_CI})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Add a CI workflow",
                summary="Add CI (for example GitHub Actions) for build and test on every change.",
                rationale=finding.description,
                category=RecommendationCategory.BUILD,
                actions=_actions(
                    (
                        "Create workflow directory",
                        "Add .github/workflows/ that installs dependencies and runs tests.",
                        None,
                        "https://docs.github.com/en/actions/quickstart",
                    ),
                    (
                        "Gate merges on CI",
                        "Require the workflow to pass before merging protected branches.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class MavenWrapperRecommendation:
    def id(self) -> str:
        return "codestrata-rec-maven-wrapper-missing"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_MVNW})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Add the Maven Wrapper",
                summary="Commit mvnw so builds use a pinned Maven version without local installs.",
                rationale=finding.description,
                category=RecommendationCategory.BUILD,
                actions=_actions(
                    (
                        "Generate Maven Wrapper",
                        "Generate the wrapper once and commit mvnw, mvnw.cmd, and .mvn/wrapper.",
                        "mvn -N wrapper:wrapper",
                        "https://maven.apache.org/wrapper/",
                    ),
                    (
                        "Update CI and docs",
                        "Prefer ./mvnw in CI and README build instructions.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class NpmLockfileRecommendation:
    def id(self) -> str:
        return "codestrata-rec-npm-lockfile-missing"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_NPM_LOCK})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Commit an npm lockfile",
                summary="Add package-lock.json (or yarn/pnpm lock) for reproducible installs.",
                rationale=finding.description,
                category=RecommendationCategory.DEPENDENCY,
                actions=_actions(
                    (
                        "Generate lockfile",
                        "Run the package manager install and commit the produced lockfile.",
                        "npm install --package-lock-only",
                        None,
                    ),
                    (
                        "Use ci installs in pipelines",
                        "Prefer npm ci (or yarn/pnpm frozen lockfile installs) in CI.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class UnsupportedSpringBootRecommendation:
    def id(self) -> str:
        return "codestrata-rec-unsupported-spring-boot"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_BOOT_UNSUPPORTED})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        version = finding.metadata.get("spring_boot_version")
        version_text = str(version) if version is not None else "2.x"
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title=f"Upgrade Spring Boot {version_text}",
                summary=(
                    "Plan and execute an upgrade from Spring Boot 2.x to a supported 3.x line."
                ),
                rationale=finding.description,
                category=RecommendationCategory.MODERNIZATION,
                priority=RecommendationPriority.HIGH,
                metadata={"spring_boot_version": version_text},
                actions=_actions(
                    (
                        "Assess current compatibility",
                        "Inventory Boot starters, plugins, and libraries for 3.x support.",
                        None,
                        "https://spring.io/projects/spring-boot",
                    ),
                    (
                        "Upgrade to supported Spring Boot 3.x",
                        "Bump the Boot parent/BOM to supported 3.x and fix build failures.",
                        None,
                        None,
                    ),
                    (
                        "Move to a supported Java version",
                        "Adopt Java 17+ (or the Boot 3.x baseline for your target release).",
                        None,
                        None,
                    ),
                    (
                        "Review Jakarta namespace migration",
                        "Replace javax.* imports with jakarta.* and update related configuration.",
                        None,
                        None,
                    ),
                    (
                        "Run tests and dependency compatibility checks",
                        "Run the full test suite and review dependency convergence.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class JavaLanguageLevelRecommendation:
    """Recommend only when Java language level is missing or legacy (for example Java 8)."""

    def id(self) -> str:
        return "codestrata-rec-java-language-level"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_JAVA})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        version = finding.metadata.get("java_version")
        is_java_8 = finding.metadata.get("is_java_8") is True
        major = finding.metadata.get("java_major")
        missing = version is None
        old = is_java_8 or (isinstance(major, int) and major < 17)
        if not missing and not old:
            return ()
        if missing:
            title = "Declare a Java language level"
            summary = "Set java.version (or compiler release/source) in the Maven POM."
            rationale = (
                "Java is present but no Maven language-level property was extracted, "
                "so build and runtime baselines are ambiguous."
            )
            actions = _actions(
                (
                    "Set java.version",
                    "Add java.version=17 (or your target LTS) under Maven properties.",
                    None,
                    None,
                ),
                (
                    "Align CI JDK",
                    "Ensure CI and local toolchains use the same JDK major version.",
                    None,
                    None,
                ),
            )
        else:
            title = f"Upgrade Java language level from {version}"
            summary = f"Move off Java {version} onto a supported LTS baseline (17+)."
            rationale = finding.description
            actions = _actions(
                (
                    "Choose target LTS",
                    "Select Java 17 or 21 based on framework and library support.",
                    None,
                    None,
                ),
                (
                    "Update Maven language level",
                    "Set java.version / maven.compiler.release and fix compilation issues.",
                    None,
                    None,
                ),
                (
                    "Validate runtime",
                    "Re-run tests on the target JDK and update CI images.",
                    None,
                    None,
                ),
            )
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title=title,
                summary=summary,
                rationale=rationale,
                category=RecommendationCategory.MODERNIZATION,
                priority=(RecommendationPriority.HIGH if old else RecommendationPriority.MEDIUM),
                actions=actions,
                metadata={
                    "java_version": version,
                    "is_java_8": is_java_8,
                    "missing_language_level": missing,
                },
            ),
        )


class MissingNodeEngineRecommendation:
    def id(self) -> str:
        return "codestrata-rec-missing-node-engine"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_NODE_ENGINE_MISSING})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Declare engines.node",
                summary="Add an engines.node constraint so tooling and CI pin a Node baseline.",
                rationale=finding.description,
                category=RecommendationCategory.DEPENDENCY,
                actions=_actions(
                    (
                        "Add engines.node",
                        "Declare a supported Node major in engines.node (for example >=18).",
                        None,
                        "https://docs.npmjs.com/cli/v10/configuring-npm/package-json#engines",
                    ),
                    (
                        "Align local and CI Node versions",
                        "Use the same Node major in developer environments and CI images.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class LargeRepositoryRecommendation:
    def id(self) -> str:
        return "codestrata-rec-large-repository"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset({_LARGE})

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        _ = context
        file_count = finding.metadata.get("file_count")
        return (
            _base(
                provider_id=self.id(),
                finding=finding,
                title="Assess repository modularization",
                summary="Review whether the large inventory should be split or scoped.",
                rationale=finding.description,
                category=RecommendationCategory.MAINTAINABILITY,
                priority=RecommendationPriority.LOW,
                metadata={"file_count": file_count},
                actions=_actions(
                    (
                        "Map bounded contexts",
                        "Identify cohesive modules that can be modernized independently.",
                        None,
                        None,
                    ),
                    (
                        "Reduce scan noise",
                        "Exclude generated or vendor trees from assessment scope when appropriate.",
                        None,
                        None,
                    ),
                ),
            ),
        )


class CorrelationAwareTransportVerificationRecommendation:
    """One Recommendation for correlated TLS + hostname verification Findings."""

    def id(self) -> str:
        return "codestrata-rec-correlation-transport-verification"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset(
            {
                "security.tls-verification-disabled",
                "security.hostname-verification-disabled",
            }
        )

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        # Emit once from the lexicographically first correlated finding.
        related = tuple(getattr(finding, "correlated_finding_ids", ()) or ())
        if not related:
            return ()
        peers = [
            item
            for item in context.findings
            if item.id in related
            and item.rule_id
            in {
                "security.tls-verification-disabled",
                "security.hostname-verification-disabled",
            }
            and item.rule_id != finding.rule_id
        ]
        if not peers:
            return ()
        members = tuple(sorted((finding, *peers), key=lambda item: item.id))
        if finding.id != members[0].id:
            return ()
        finding_ids = tuple(item.id for item in members)
        from codestrata.application.traceability.recommendation import (
            select_primary_finding_id,
        )
        from codestrata.domain.findings.enums import FindingSeverity

        _sev_rank = {
            FindingSeverity.INFORMATIONAL: 0,
            FindingSeverity.LOW: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.HIGH: 3,
            FindingSeverity.CRITICAL: 4,
        }
        highest = max(members, key=lambda item: _sev_rank.get(item.severity, 0))

        return (
            Recommendation.create(
                provider_id=self.id(),
                title="Restore transport verification controls",
                summary=(
                    "TLS verification and hostname verification are both disabled "
                    "on the same configuration boundary."
                ),
                rationale=(
                    "Correlated Security Findings share a configuration subject; "
                    "restore verification together."
                ),
                priority=priority_from_finding_severity(highest.severity),
                category=RecommendationCategory.MODERNIZATION,
                related_finding_ids=finding_ids,
                supporting_finding_ids=finding_ids,
                primary_finding_id=select_primary_finding_id(members) or members[0].id,
                actions=_actions(
                    (
                        "Re-enable verification",
                        "Restore TLS and hostname verification on the shared boundary.",
                        None,
                        None,
                    ),
                ),
                subject_keys=("correlation", "transport-verification", *finding_ids),
                metadata={"correlation_aware": "true"},
            ),
        )


class CorrelationAwareDependencyNormalizationRecommendation:
    """One Recommendation for correlated duplicate + conflicting dependency Findings."""

    def id(self) -> str:
        return "codestrata-rec-correlation-dependency-normalization"

    def supported_finding_rule_ids(self) -> frozenset[str]:
        return frozenset(
            {
                "dependency.duplicate-declaration",
                "dependency.conflicting-exact-versions",
            }
        )

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        related = tuple(getattr(finding, "correlated_finding_ids", ()) or ())
        if not related:
            return ()
        peers = [
            item
            for item in context.findings
            if item.id in related
            and item.rule_id
            in {
                "dependency.duplicate-declaration",
                "dependency.conflicting-exact-versions",
            }
            and item.rule_id != finding.rule_id
        ]
        if not peers:
            return ()
        members = tuple(sorted((finding, *peers), key=lambda item: item.id))
        if finding.id != members[0].id:
            return ()
        finding_ids = tuple(item.id for item in members)
        from codestrata.application.traceability.recommendation import (
            select_primary_finding_id,
        )
        from codestrata.domain.findings.enums import FindingSeverity

        _sev_rank = {
            FindingSeverity.INFORMATIONAL: 0,
            FindingSeverity.LOW: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.HIGH: 3,
            FindingSeverity.CRITICAL: 4,
        }
        highest = max(members, key=lambda item: _sev_rank.get(item.severity, 0))

        return (
            Recommendation.create(
                provider_id=self.id(),
                title="Normalize duplicate dependency declarations",
                summary=(
                    "Duplicate declarations and conflicting exact versions affect "
                    "the same dependency identity."
                ),
                rationale=(
                    "Correlated Dependency Findings share dependency identity; "
                    "normalize declarations in one change."
                ),
                priority=priority_from_finding_severity(highest.severity),
                category=RecommendationCategory.DEPENDENCY,
                related_finding_ids=finding_ids,
                supporting_finding_ids=finding_ids,
                primary_finding_id=select_primary_finding_id(members) or members[0].id,
                actions=_actions(
                    (
                        "Consolidate declarations",
                        "Keep one declaration with a single exact version in scope.",
                        None,
                        None,
                    ),
                ),
                subject_keys=("correlation", "dependency-normalization", *finding_ids),
                metadata={"correlation_aware": "true"},
            ),
        )


def builtin_recommendation_providers() -> tuple[object, ...]:
    """Return the ordered builtin recommendation provider set."""

    return (
        MissingReadmeRecommendation(),
        MissingLicenseRecommendation(),
        MissingTestsRecommendation(),
        MissingCiRecommendation(),
        MavenWrapperRecommendation(),
        NpmLockfileRecommendation(),
        UnsupportedSpringBootRecommendation(),
        JavaLanguageLevelRecommendation(),
        MissingNodeEngineRecommendation(),
        LargeRepositoryRecommendation(),
        CorrelationAwareTransportVerificationRecommendation(),
        CorrelationAwareDependencyNormalizationRecommendation(),
    )
