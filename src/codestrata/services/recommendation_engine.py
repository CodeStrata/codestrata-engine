"""Deterministic modernization recommendation engine."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.models import (
    Evidence,
    Finding,
    Priority,
    Recommendation,
    RepositoryFacts,
    Technology,
)
from codestrata.models.enums import (
    Effort,
    FindingSource,
    RecommendationCategory,
    Risk,
    Severity,
)
from codestrata.models.normalized_facts import StructureFacts

# Recommend expanding coverage when tests are under 10% of source files.
_LOW_TEST_RATIO_THRESHOLD = 0.1


class ModernizationRecommendationEngine:
    """Generate prioritized modernization recommendations from normalized inputs."""

    def generate(
        self,
        facts: RepositoryFacts,
        findings: Sequence[Finding],
        technologies: Sequence[Technology],
    ) -> list[Recommendation]:
        """Generate deterministic recommendations from facts and findings."""

        del technologies

        candidates = [
            recommendation
            for recommendation in (
                self._recommend_no_tests(facts),
                self._recommend_low_test_ratio(facts),
                self._recommend_secret_findings(facts, findings),
                self._recommend_weak_crypto(facts, findings),
                self._recommend_dangerous_execution(facts, findings),
                self._recommend_cloud_baseline(facts),
                self._recommend_docker_without_deployment(facts),
                self._recommend_kubernetes_without_helm(facts),
                self._recommend_no_ci(facts),
                self._recommend_ci_without_deployment(facts),
                self._recommend_architecture_separation(facts),
                self._recommend_multi_application(facts),
                self._recommend_outdated_dependencies(facts),
                *self._recommend_pmd_groups(findings),
            )
            if recommendation is not None
        ]

        return self._deduplicate_and_sort(candidates)

    def _recommend_no_tests(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        structure = facts.structure

        if structure is None or structure.has_tests is not False:
            return None

        test_count = structure.test_file_count
        observation = "Repository structure facts indicate no automated tests were detected" + (
            f" (test_file_count={test_count})." if test_count is not None else "."
        )

        return self._recommendation(
            rule_id="REC.TESTING.001",
            title="Establish automated tests before modernization",
            description=(
                "Introduce an automated test suite covering critical application "
                "behavior before broader modernization changes."
            ),
            rationale=(
                f"{observation} Modernization without regression coverage "
                "increases the likelihood of undetected behavior changes."
            ),
            priority=Priority.HIGH,
            category=RecommendationCategory.TESTING,
            effort=Effort.MEDIUM,
            risk=Risk.HIGH,
            evidence=[
                self._fact_evidence(f"structure.has_tests=false; test_file_count={test_count!s}")
            ],
            metadata={"has_tests": False, "test_file_count": test_count},
        )

    def _recommend_low_test_ratio(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        structure = facts.structure

        if structure is None:
            return None

        if structure.has_tests is not True:
            return None

        source_count = structure.source_file_count
        test_count = structure.test_file_count

        if source_count is None or test_count is None:
            return None

        if source_count <= 0:
            return None

        ratio = test_count / source_count

        if ratio >= _LOW_TEST_RATIO_THRESHOLD:
            return None

        return self._recommendation(
            rule_id="REC.TESTING.002",
            title="Expand regression test coverage",
            description=(
                "Increase automated regression coverage for critical paths so "
                "modernization changes can be validated safely."
            ),
            rationale=(
                f"Detected {test_count} test file(s) against {source_count} "
                f"source file(s) (ratio={ratio:.2f}, threshold="
                f"{_LOW_TEST_RATIO_THRESHOLD:.2f}). Low coverage relative to "
                "source size raises modernization risk."
            ),
            priority=Priority.MEDIUM,
            category=RecommendationCategory.TESTING,
            effort=Effort.MEDIUM,
            risk=Risk.MEDIUM,
            evidence=[
                self._fact_evidence(
                    "structure.has_tests=true; "
                    f"source_file_count={source_count}; "
                    f"test_file_count={test_count}; "
                    f"ratio={ratio:.2f}"
                )
            ],
            metadata={
                "source_file_count": source_count,
                "test_file_count": test_count,
                "test_to_source_ratio": round(ratio, 4),
                "threshold": _LOW_TEST_RATIO_THRESHOLD,
            },
        )

    def _recommend_secret_findings(
        self,
        facts: RepositoryFacts,
        findings: Sequence[Finding],
    ) -> Recommendation | None:
        security = facts.security

        if security is None or not security.secret_finding_count:
            return None

        related = self._finding_ids(
            findings,
            {"SEC002", "SEC003", "SEC004"},
        )

        return self._recommendation(
            rule_id="REC.SECURITY.001",
            title="Rotate credentials and remove committed secrets",
            description=(
                "Remove committed secrets from the repository, rotate exposed "
                "credentials, and move sensitive values to a secrets manager "
                "or secure configuration store."
            ),
            rationale=(
                f"Security facts report {security.secret_finding_count} "
                "secret-related finding(s). Exposed credentials can enable "
                "unauthorized access and must be remediated before other "
                "modernization work."
            ),
            priority=Priority.CRITICAL,
            category=RecommendationCategory.SECURITY,
            effort=Effort.SMALL,
            risk=Risk.HIGH,
            evidence=[
                self._fact_evidence(
                    f"security.secret_finding_count={security.secret_finding_count}"
                )
            ],
            related_finding_ids=related,
            metadata={"secret_finding_count": security.secret_finding_count},
        )

    def _recommend_weak_crypto(
        self,
        facts: RepositoryFacts,
        findings: Sequence[Finding],
    ) -> Recommendation | None:
        security = facts.security

        if security is None or not security.weak_crypto_count:
            return None

        related = self._finding_ids(findings, {"SEC005"})

        return self._recommendation(
            rule_id="REC.SECURITY.002",
            title="Replace weak cryptographic algorithms",
            description=(
                "Replace weak cryptographic algorithms with current, approved "
                "alternatives and verify dependent integrations still function."
            ),
            rationale=(
                f"Security facts report {security.weak_crypto_count} weak "
                "cryptography finding(s). Continuing to use weak algorithms "
                "increases confidentiality and integrity risk."
            ),
            priority=Priority.HIGH,
            category=RecommendationCategory.SECURITY,
            effort=Effort.MEDIUM,
            risk=Risk.HIGH,
            evidence=[
                self._fact_evidence(f"security.weak_crypto_count={security.weak_crypto_count}")
            ],
            related_finding_ids=related,
            metadata={"weak_crypto_count": security.weak_crypto_count},
        )

    def _recommend_dangerous_execution(
        self,
        facts: RepositoryFacts,
        findings: Sequence[Finding],
    ) -> Recommendation | None:
        security = facts.security

        if security is None or not security.dangerous_execution_count:
            return None

        related = self._finding_ids(findings, {"SEC006"})

        return self._recommendation(
            rule_id="REC.SECURITY.003",
            title="Remove or constrain unsafe execution paths",
            description=(
                "Remove or tightly constrain dynamic execution patterns such as "
                "eval/exec/shell invocation, and replace them with safer APIs "
                "where possible."
            ),
            rationale=(
                f"Security facts report {security.dangerous_execution_count} "
                "dangerous-execution finding(s). Unconstrained execution paths "
                "are a common injection and privilege-escalation vector."
            ),
            priority=Priority.HIGH,
            category=RecommendationCategory.SECURITY,
            effort=Effort.MEDIUM,
            risk=Risk.HIGH,
            evidence=[
                self._fact_evidence(
                    f"security.dangerous_execution_count={security.dangerous_execution_count}"
                )
            ],
            related_finding_ids=related,
            metadata={
                "dangerous_execution_count": security.dangerous_execution_count,
            },
        )

    def _recommend_cloud_baseline(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        cloud = facts.cloud

        if cloud is None:
            return None

        signals = (
            cloud.has_docker,
            cloud.has_kubernetes,
            cloud.has_terraform,
            cloud.has_cloudformation,
            cloud.has_serverless,
        )

        if any(signal is None for signal in signals):
            return None

        if any(signals):
            return None

        return self._recommendation(
            rule_id="REC.CLOUD.001",
            title="Create a deployment baseline for modernization",
            description=(
                "Establish a minimal, repeatable deployment baseline "
                "(for example packaging, environment configuration, and a "
                "documented release path) so modernization changes can be "
                "validated outside local developer machines. This does not "
                "require adopting Kubernetes."
            ),
            rationale=(
                "Cloud readiness facts show no Docker, Kubernetes, Terraform, "
                "CloudFormation, or serverless assets. Without a deployment "
                "baseline, modernization delivery remains difficult to "
                "reproduce and validate."
            ),
            priority=Priority.MEDIUM,
            category=RecommendationCategory.CLOUD,
            effort=Effort.MEDIUM,
            risk=Risk.MEDIUM,
            evidence=[
                self._fact_evidence(
                    "cloud.has_docker=false; cloud.has_kubernetes=false; "
                    "cloud.has_terraform=false; cloud.has_cloudformation=false; "
                    "cloud.has_serverless=false"
                )
            ],
            metadata={"cloud_capabilities": list(cloud.cloud_capabilities)},
        )

    def _recommend_docker_without_deployment(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        cloud = facts.cloud
        cicd = facts.cicd

        if cloud is None or cloud.has_docker is not True:
            return None

        if cicd is None or cicd.has_deployment_workflow is not False:
            return None

        return self._recommendation(
            rule_id="REC.CLOUD.002",
            title="Automate container image build and deployment",
            description=(
                "Add a controlled workflow that builds the container image and "
                "deploys it to a target environment using existing Docker assets."
            ),
            rationale=(
                "Docker assets were detected, but no deployment workflow was "
                "found. Automating image build and deployment reduces manual "
                "release risk while reusing the existing packaging approach."
            ),
            priority=Priority.MEDIUM,
            category=RecommendationCategory.CLOUD,
            effort=Effort.MEDIUM,
            risk=Risk.LOW,
            evidence=[
                self._fact_evidence("cloud.has_docker=true; cicd.has_deployment_workflow=false")
            ],
            metadata={
                "has_docker": True,
                "has_deployment_workflow": False,
            },
        )

    def _recommend_kubernetes_without_helm(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        cloud = facts.cloud

        if cloud is None:
            return None

        if cloud.has_kubernetes is not True:
            return None

        if cloud.has_helm is not False:
            return None

        return self._recommendation(
            rule_id="REC.CLOUD.003",
            title="Evaluate reusable Kubernetes deployment packaging",
            description=(
                "Evaluate whether reusable deployment packaging (such as Helm "
                "charts or an equivalent templating approach) would reduce "
                "duplication across environments. Helm is optional, not mandatory."
            ),
            rationale=(
                "Kubernetes assets were detected without Helm packaging. "
                "Reusable packaging can improve consistency, but teams may "
                "already use an equivalent approach."
            ),
            priority=Priority.LOW,
            category=RecommendationCategory.CLOUD,
            effort=Effort.MEDIUM,
            risk=Risk.LOW,
            evidence=[self._fact_evidence("cloud.has_kubernetes=true; cloud.has_helm=false")],
            metadata={"has_kubernetes": True, "has_helm": False},
        )

    def _recommend_no_ci(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        cicd = facts.cicd

        if cicd is None or cicd.has_ci is not False:
            return None

        return self._recommendation(
            rule_id="REC.CICD.001",
            title="Establish CI build, test, and quality gates",
            description=(
                "Introduce continuous integration that builds the application, "
                "runs automated tests, and applies basic quality gates on every "
                "change."
            ),
            rationale=(
                "CI/CD facts indicate no CI platform or pipeline was detected. "
                "Without automated gates, modernization changes are harder to "
                "validate consistently."
            ),
            priority=Priority.HIGH,
            category=RecommendationCategory.CI_CD,
            effort=Effort.MEDIUM,
            risk=Risk.MEDIUM,
            evidence=[self._fact_evidence("cicd.has_ci=false")],
            metadata={"has_ci": False},
        )

    def _recommend_ci_without_deployment(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        cicd = facts.cicd

        if cicd is None:
            return None

        if cicd.has_ci is not True:
            return None

        if cicd.has_deployment_workflow is not False:
            return None

        platforms = cicd.ci_platforms or cicd.providers

        return self._recommendation(
            rule_id="REC.CICD.002",
            title="Add controlled deployment automation to CI",
            description=(
                "Extend existing CI with a controlled deployment workflow that "
                "promotes validated builds to a target environment."
            ),
            rationale=(
                "CI was detected"
                + (f" ({', '.join(platforms)})" if platforms else "")
                + ", but no deployment workflow was found. Adding controlled "
                "deployment automation closes the gap between verified builds "
                "and repeatable releases."
            ),
            priority=Priority.MEDIUM,
            category=RecommendationCategory.CI_CD,
            effort=Effort.MEDIUM,
            risk=Risk.MEDIUM,
            evidence=[
                self._fact_evidence(
                    "cicd.has_ci=true; cicd.has_deployment_workflow=false"
                    + (f"; ci_platforms={','.join(platforms)}" if platforms else "")
                )
            ],
            metadata={
                "has_ci": True,
                "has_deployment_workflow": False,
                "ci_platforms": list(platforms),
            },
        )

    def _recommend_architecture_separation(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        architecture = facts.architecture
        structure = facts.structure

        if architecture is None:
            return None

        if not self._is_application_repository(structure):
            return None

        layer_flags = (
            architecture.has_api_layer,
            architecture.has_service_layer,
            architecture.has_persistence_layer,
        )

        if any(flag is None for flag in layer_flags):
            return None

        if any(layer_flags):
            return None

        return self._recommendation(
            rule_id="REC.ARCHITECTURE.001",
            title="Review separation of concerns across application layers",
            description=(
                "Review current module boundaries and introduce clearer "
                "separation between interface, business logic, and persistence "
                "concerns where evidence supports it."
            ),
            rationale=(
                "Architecture facts show no detected API, service, or "
                "persistence layering in an application repository. Weak "
                "separation of concerns can increase change risk during "
                "modernization."
            ),
            priority=Priority.MEDIUM,
            category=RecommendationCategory.ARCHITECTURE,
            effort=Effort.LARGE,
            risk=Risk.MEDIUM,
            evidence=[
                self._fact_evidence(
                    "architecture.has_api_layer=false; "
                    "architecture.has_service_layer=false; "
                    "architecture.has_persistence_layer=false"
                )
            ],
            metadata={
                "has_api_layer": False,
                "has_service_layer": False,
                "has_persistence_layer": False,
            },
        )

    def _recommend_multi_application(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        architecture = facts.architecture

        if architecture is None or architecture.is_multi_application is not True:
            return None

        application_count = (
            facts.structure.application_count if facts.structure is not None else None
        )

        return self._recommendation(
            rule_id="REC.ARCHITECTURE.002",
            title="Document ownership and deployment boundaries",
            description=(
                "Document ownership, deployment units, and shared-contract "
                "boundaries for each application in the repository. This does "
                "not require splitting into microservices."
            ),
            rationale=(
                "Architecture facts indicate a multi-application repository"
                + (
                    f" (application_count={application_count})"
                    if application_count is not None
                    else ""
                )
                + ". Clear ownership and deployment boundaries reduce "
                "coordination risk during modernization."
            ),
            priority=Priority.LOW,
            category=RecommendationCategory.ARCHITECTURE,
            effort=Effort.SMALL,
            risk=Risk.LOW,
            evidence=[
                self._fact_evidence(
                    "architecture.is_multi_application=true"
                    + (
                        f"; structure.application_count={application_count}"
                        if application_count is not None
                        else ""
                    )
                )
            ],
            metadata={
                "is_multi_application": True,
                "application_count": application_count,
            },
        )

    def _recommend_outdated_dependencies(
        self,
        facts: RepositoryFacts,
    ) -> Recommendation | None:
        dependencies = facts.dependencies

        if dependencies is None or not dependencies.outdated_dependencies:
            return None

        outdated = list(dependencies.outdated_dependencies)
        count = len(outdated)

        if count <= 5:
            effort = Effort.SMALL
        elif count <= 20:
            effort = Effort.MEDIUM
        else:
            effort = Effort.LARGE

        sample = ", ".join(outdated[:10])

        return self._recommendation(
            rule_id="REC.DEPENDENCIES.001",
            title="Plan upgrades for outdated dependencies",
            description=(
                "Create a prioritized dependency upgrade plan for the outdated "
                "packages already identified by deterministic analysis."
            ),
            rationale=(
                f"Dependency facts list {count} outdated dependency name(s)"
                + (f" (sample: {sample})" if sample else "")
                + ". Deferred upgrades increase security and compatibility risk "
                "during modernization."
            ),
            priority=Priority.HIGH,
            category=RecommendationCategory.DEPENDENCIES,
            effort=effort,
            risk=Risk.MEDIUM,
            evidence=[
                self._fact_evidence(
                    f"dependencies.outdated_dependencies_count={count}; sample={sample or 'none'}"
                )
            ],
            metadata={
                "outdated_dependency_count": count,
                "outdated_dependencies": outdated,
            },
        )

    def _recommend_pmd_groups(
        self,
        findings: Sequence[Finding],
    ) -> list[Recommendation]:
        """Create at most one recommendation per high-value PMD finding group."""

        recommendations: list[Recommendation] = []
        seen_rules: set[str] = set()

        for finding in findings:
            if finding.source != FindingSource.EXTERNAL_STATIC_ANALYSIS:
                continue
            rule_id = finding.rule_id or ""
            if not rule_id.startswith("PMD.") or rule_id in seen_rules:
                continue
            visibility = str(finding.metadata.get("customer_visibility") or "")
            relevance = str(finding.metadata.get("modernization_relevance") or "")
            if visibility not in {"primary", "supporting"}:
                continue
            if relevance not in {"high", "medium"}:
                continue
            if finding.severity not in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
                continue

            seen_rules.add(rule_id)
            occurrence = int(finding.metadata.get("occurrence_count") or 1)
            files = int(finding.metadata.get("affected_file_count") or len(finding.evidence))
            priority = {
                Severity.CRITICAL: Priority.CRITICAL,
                Severity.HIGH: Priority.HIGH,
                Severity.MEDIUM: Priority.MEDIUM,
            }[finding.severity]
            category = (
                RecommendationCategory.SECURITY
                if finding.category.value == "security"
                else RecommendationCategory.ARCHITECTURE
            )
            recommendations.append(
                self._recommendation(
                    rule_id=f"REC.{rule_id}",
                    title=f"Address PMD pattern: {finding.title}",
                    description=(
                        f"Remediate the recurring PMD finding '{finding.title}' "
                        f"({occurrence} occurrence{'s' if occurrence != 1 else ''} across "
                        f"{files} file{'s' if files != 1 else ''})."
                    ),
                    rationale=(
                        "Grouped static-analysis evidence indicates a modernization-relevant "
                        f"pattern ({relevance} relevance, {visibility} visibility)."
                    ),
                    priority=priority,
                    category=category,
                    effort=Effort.MEDIUM if occurrence > 3 else Effort.SMALL,
                    risk=(
                        Risk.HIGH
                        if finding.severity in {Severity.CRITICAL, Severity.HIGH}
                        else Risk.MEDIUM
                    ),
                    evidence=list(finding.evidence[:5]),
                    related_finding_ids=[str(finding.id)],
                    metadata={
                        "pmd_rule_id": rule_id,
                        "group_id": finding.metadata.get("group_id"),
                        "occurrence_count": occurrence,
                        "affected_file_count": files,
                    },
                )
            )
        return recommendations

    @staticmethod
    def _is_application_repository(structure: StructureFacts | None) -> bool:
        if structure is None:
            return False

        if structure.source_file_count is not None and structure.source_file_count > 0:
            return True

        if structure.application_count is not None and structure.application_count > 0:
            return True

        return False

    @staticmethod
    def _finding_ids(
        findings: Sequence[Finding],
        rule_ids: set[str],
    ) -> list[str]:
        return [str(finding.id) for finding in findings if finding.rule_id in rule_ids]

    @staticmethod
    def _fact_evidence(description: str) -> Evidence:
        return Evidence(
            file_path="repository-facts",
            description=description,
        )

    @staticmethod
    def _recommendation(
        *,
        rule_id: str,
        title: str,
        description: str,
        rationale: str,
        priority: Priority,
        category: RecommendationCategory,
        effort: Effort,
        risk: Risk,
        evidence: list[Evidence],
        related_finding_ids: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Recommendation:
        return Recommendation(
            rule_id=rule_id,
            title=title,
            description=description,
            rationale=rationale,
            priority=priority,
            category=category,
            effort=effort,
            risk=risk,
            evidence=evidence,
            related_finding_ids=related_finding_ids or [],
            actions=[description],
            metadata=metadata or {},
        )

    @staticmethod
    def _deduplicate_and_sort(
        recommendations: list[Recommendation],
    ) -> list[Recommendation]:
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        risk_order = {
            Risk.HIGH: 0,
            Risk.MEDIUM: 1,
            Risk.LOW: 2,
        }

        unique: dict[str, Recommendation] = {}

        for recommendation in recommendations:
            unique.setdefault(recommendation.rule_id, recommendation)

        return sorted(
            unique.values(),
            key=lambda recommendation: (
                priority_order[recommendation.priority],
                risk_order[recommendation.risk],
                recommendation.category.value,
                recommendation.rule_id,
            ),
        )
