"""Evaluate dependency health using deterministic rules."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.models import (
    AnalyzerResult,
    DependencyFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)


class DependencyHealthAnalyzer:
    """Generate findings from dependency facts."""

    LOCKFILE_ECOSYSTEMS = {
        "npm": {"npm", "yarn", "pnpm"},
        "composer": {"composer"},
        "python": {"python"},
        "go": {"go"},
        "cargo": {"cargo"},
        "gradle": {"gradle"},
    }

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Produce health findings from previously accumulated dependency facts.

        This analyzer does not contribute new facts. It returns findings only
        so CompositeAnalyzer preserves the merged facts for later steps.
        """

        del repository
        del technologies

        if facts is None or facts.dependencies is None:
            return AnalyzerResult(
                findings=[],
                facts=RepositoryFacts(),
            )

        dependency_facts = facts.dependencies

        findings = [
            *self._find_unmanaged_versions(dependency_facts),
            *self._find_dynamic_versions(dependency_facts),
            *self._find_missing_lockfiles(dependency_facts),
        ]

        return AnalyzerResult(
            findings=findings,
            facts=RepositoryFacts(),
        )

    def _find_unmanaged_versions(
        self,
        dependency_facts: DependencyFacts,
    ) -> list[Finding]:
        """Find dependencies without explicitly managed versions."""

        findings: list[Finding] = []

        for dependency in dependency_facts.dependencies:
            if not dependency.unmanaged_version:
                continue

            description = (
                f"{dependency.name} in "
                f"{dependency.manifest_path} does not declare "
                "an explicit version."
            )

            findings.append(
                Finding(
                    rule_id="DEP001",
                    title="Dependency has no explicit version",
                    description=description,
                    category=FindingCategory.DEPENDENCY,
                    severity=Severity.MEDIUM,
                    source=FindingSource.DETERMINISTIC,
                    evidence=[
                        Evidence(
                            file_path=dependency.manifest_path,
                            description=description,
                            detected_value=dependency.name,
                        )
                    ],
                    affected_technologies=[dependency.ecosystem],
                    metadata={
                        "dependency": dependency.name,
                        "ecosystem": dependency.ecosystem,
                        "scope": dependency.scope,
                        "manifest_path": dependency.manifest_path,
                    },
                )
            )

        return findings

    def _find_dynamic_versions(
        self,
        dependency_facts: DependencyFacts,
    ) -> list[Finding]:
        """Find dependencies that allow non-deterministic versions."""

        findings: list[Finding] = []

        for dependency in dependency_facts.dependencies:
            if not dependency.dynamic_version:
                continue

            description = (
                f"{dependency.name} in "
                f"{dependency.manifest_path} uses version "
                f"{dependency.version!r}."
            )

            findings.append(
                Finding(
                    rule_id="DEP002",
                    title="Dependency uses a dynamic version",
                    description=description,
                    category=FindingCategory.DEPENDENCY,
                    severity=Severity.MEDIUM,
                    source=FindingSource.DETERMINISTIC,
                    evidence=[
                        Evidence(
                            file_path=dependency.manifest_path,
                            description=description,
                            detected_value=dependency.version,
                        )
                    ],
                    affected_technologies=[dependency.ecosystem],
                    metadata={
                        "dependency": dependency.name,
                        "version": dependency.version,
                        "ecosystem": dependency.ecosystem,
                        "scope": dependency.scope,
                        "manifest_path": dependency.manifest_path,
                    },
                )
            )

        return findings

    def _find_missing_lockfiles(
        self,
        dependency_facts: DependencyFacts,
    ) -> list[Finding]:
        """Find ecosystems where dependency locking is not configured."""

        # Maven does not use a conventional lockfile; do not treat it as missing.
        manifest_ecosystems = {
            manifest.ecosystem for manifest in dependency_facts.manifests if not manifest.lockfile
        }

        lockfile_ecosystems = {
            manifest.ecosystem for manifest in dependency_facts.manifests if manifest.lockfile
        }

        findings: list[Finding] = []

        for ecosystem in sorted(manifest_ecosystems):
            accepted_lockfile_ecosystems = self.LOCKFILE_ECOSYSTEMS.get(ecosystem)

            if accepted_lockfile_ecosystems is None:
                continue

            if lockfile_ecosystems & accepted_lockfile_ecosystems:
                continue

            manifest_paths = sorted(
                manifest.path
                for manifest in dependency_facts.manifests
                if (manifest.ecosystem == ecosystem and not manifest.lockfile)
            )

            severity = (
                Severity.MEDIUM
                if self._ecosystem_has_dependency_risk(
                    ecosystem=ecosystem,
                    dependency_facts=dependency_facts,
                )
                else Severity.LOW
            )

            description = (
                f"{ecosystem} dependency locking is not configured for: "
                f"{', '.join(manifest_paths)}."
            )

            findings.append(
                Finding(
                    rule_id="DEP003",
                    title="Dependency locking is not configured",
                    description=description,
                    category=FindingCategory.DEPENDENCY,
                    severity=severity,
                    source=FindingSource.DETERMINISTIC,
                    evidence=[
                        Evidence(
                            file_path=manifest_path,
                            description=description,
                        )
                        for manifest_path in manifest_paths
                    ],
                    affected_technologies=[ecosystem],
                    metadata={
                        "ecosystem": ecosystem,
                        "manifest_paths": manifest_paths,
                    },
                )
            )

        return findings

    def _ecosystem_has_dependency_risk(
        self,
        ecosystem: str,
        dependency_facts: DependencyFacts,
    ) -> bool:
        """Return whether an ecosystem has dynamic or unmanaged versions."""

        related_ecosystems = self.LOCKFILE_ECOSYSTEMS.get(ecosystem, {ecosystem})

        for dependency in dependency_facts.dependencies:
            if dependency.ecosystem not in related_ecosystems and dependency.ecosystem != ecosystem:
                continue

            if dependency.dynamic_version or dependency.unmanaged_version:
                return True

        return False
