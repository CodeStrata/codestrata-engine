"""Builtin deterministic Assessment Graph rules."""

from __future__ import annotations

from codestrata.domain.findings import Finding, FindingCategory, FindingEvidence, FindingSeverity
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.rules import Rule, RuleContext, RuleResult

_ALL_LANGUAGES: frozenset[str] = frozenset()
_JAVA: frozenset[str] = frozenset({"java"})


def _evidence(
    *,
    evidence_type: str,
    source_id: str,
    path: str | None = None,
    excerpt: str | None = None,
) -> FindingEvidence:
    return FindingEvidence(
        evidence_type=evidence_type,
        source_id=source_id,
        path=path,
        excerpt=excerpt,
    )


class MissingReadmeRule:
    def id(self) -> str:
        return "codestrata-rule-missing-readme"

    def name(self) -> str:
        return "Missing README"

    def description(self) -> str:
        return "Flags repositories that do not include a README file."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if context.has_basename("readme", "readme.md", "readme.txt", "readme.rst"):
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Missing README",
            description="No README file was found in the repository inventory.",
            severity=FindingSeverity.LOW,
            category=FindingCategory.DOCUMENTATION,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt="README basename not present in inventory paths",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "readme"),
            metadata={"checked_basenames": ["readme", "readme.md", "readme.txt", "readme.rst"]},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class MissingLicenseRule:
    def id(self) -> str:
        return "codestrata-rule-missing-license"

    def name(self) -> str:
        return "Missing LICENSE"

    def description(self) -> str:
        return "Flags repositories that do not include a LICENSE file."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if context.has_basename(
            "license",
            "license.md",
            "license.txt",
            "copying",
            "copying.md",
        ):
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Missing LICENSE",
            description="No LICENSE file was found in the repository inventory.",
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.GOVERNANCE,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt="LICENSE basename not present in inventory paths",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "license"),
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class MissingTestsRule:
    def id(self) -> str:
        return "codestrata-rule-missing-tests"

    def name(self) -> str:
        return "Missing tests"

    def description(self) -> str:
        return "Flags repositories with no detected test files or test directories."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if context.test_file_count() > 0:
            return RuleResult(rule_id=self.id(), findings=())
        if context.source_file_count() == 0:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no source files to assess for tests",
            )
        finding = Finding.create(
            rule_id=self.id(),
            title="Missing tests",
            description=(
                "No test files or conventional test directories were found "
                "while source files are present."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.TESTING,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt=(f"source_files={context.source_file_count()} test_files=0"),
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "tests"),
            metadata={"source_file_count": context.source_file_count()},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class LargeRepositoryRule:
    """Warn when inventory file count exceeds a deterministic threshold."""

    THRESHOLD = 200

    def id(self) -> str:
        return "codestrata-rule-large-repository"

    def name(self) -> str:
        return "Large repository"

    def description(self) -> str:
        return f"Flags repositories whose inventory contains more than {self.THRESHOLD} files."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        count = context.file_count()
        if count <= self.THRESHOLD:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Large repository",
            description=(
                f"Repository inventory contains {count} files, which exceeds "
                f"the warning threshold of {self.THRESHOLD}."
            ),
            severity=FindingSeverity.LOW,
            category=FindingCategory.MAINTAINABILITY,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt=f"file_count={count} threshold={self.THRESHOLD}",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "large-repo"),
            metadata={"file_count": count, "threshold": self.THRESHOLD},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class MavenWrapperMissingRule:
    def id(self) -> str:
        return "codestrata-rule-maven-wrapper-missing"

    def name(self) -> str:
        return "Maven Wrapper missing"

    def description(self) -> str:
        return "Flags Maven projects that do not include the Maven Wrapper scripts."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if not context.has_maven_project():
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="not a Maven project",
            )
        if context.has_basename("mvnw", "mvnw.cmd"):
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Maven Wrapper missing",
            description=(
                "A Maven project was detected, but mvnw / mvnw.cmd were not found "
                "in the repository inventory."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.BUILD,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt="pom.xml or maven binding present without Maven Wrapper",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "mvnw"),
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class JavaDetectedRule:
    """Signals Java presence and reports extracted language level when known."""

    def id(self) -> str:
        return "codestrata-rule-java-detected"

    def name(self) -> str:
        return "Java detected"

    def description(self) -> str:
        return (
            "Flags repositories bound to the Java language concept and reports "
            "Maven-declared Java language level when available."
        )

    def supported_languages(self) -> frozenset[str]:
        return _JAVA

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("java")
        java_version = context.java_version()
        if not bindings and java_version is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        version_text = java_version.raw if java_version is not None else None
        if version_text is not None:
            description = f"Java is present and Maven declares language level {version_text}."
            title = f"Java {version_text} detected"
        else:
            description = (
                "The Assessment Graph binds repository observations to the Java "
                "language concept. No Maven Java language-level property was found."
            )
            title = "Java detected"
        finding = Finding.create(
            rule_id=self.id(),
            title=title,
            description=description,
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.MODERNIZATION,
            evidence=tuple(
                (
                    *(
                        _evidence(
                            evidence_type="knowledge_binding",
                            source_id=binding.binding_id,
                            excerpt=f"matched_key={binding.matched_key}",
                        )
                        for binding in bindings
                    ),
                    *(
                        (
                            _evidence(
                                evidence_type="dependency_version",
                                source_id="dependency:jvm:java",
                                excerpt=f"java.version={version_text}",
                            ),
                        )
                        if version_text is not None
                        else ()
                    ),
                )
            ),
            affected_assessment_node_ids=tuple(
                sorted(
                    {node.root: node for node in affected}.values(),
                    key=lambda node: node.root,
                )
            ),
            subject_keys=(
                "java",
                *(binding.binding_id for binding in bindings),
                *(("java-version", version_text) if version_text is not None else ()),
            ),
            metadata={
                "matched_binding_count": len(bindings),
                "java_version": version_text,
                "java_major": java_version.major if java_version is not None else None,
                "is_java_8": java_version.is_java_8() if java_version is not None else None,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class SpringBootDetectedRule:
    def id(self) -> str:
        return "codestrata-rule-spring-boot-detected"

    def name(self) -> str:
        return "Spring Boot detected"

    def description(self) -> str:
        return (
            "Flags repositories bound to Spring Boot and reports the extracted "
            "Spring Boot version when available."
        )

    def supported_languages(self) -> frozenset[str]:
        return _JAVA

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("spring-boot")
        boot_version = context.spring_boot_version()
        if not bindings and boot_version is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        version_text = boot_version.raw if boot_version is not None else None
        if version_text is not None:
            title = f"Spring Boot {version_text} detected"
            description = f"Spring Boot is present at version {version_text}."
        else:
            title = "Spring Boot detected"
            description = (
                "The Assessment Graph binds repository observations to Spring Boot. "
                "No explicit Spring Boot version was extracted from Maven manifests."
            )
        finding = Finding.create(
            rule_id=self.id(),
            title=title,
            description=description,
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.MODERNIZATION,
            evidence=tuple(
                (
                    *(
                        _evidence(
                            evidence_type="knowledge_binding",
                            source_id=binding.binding_id,
                            excerpt=f"matched_key={binding.matched_key}",
                        )
                        for binding in bindings
                    ),
                    *(
                        (
                            _evidence(
                                evidence_type="dependency_version",
                                source_id="dependency:maven:spring-boot",
                                excerpt=f"spring-boot={version_text}",
                            ),
                        )
                        if version_text is not None
                        else ()
                    ),
                )
            ),
            affected_assessment_node_ids=tuple(
                sorted(
                    {node.root: node for node in affected}.values(),
                    key=lambda node: node.root,
                )
            ),
            subject_keys=(
                "spring-boot",
                *(binding.binding_id for binding in bindings),
                *(("spring-boot-version", version_text) if version_text is not None else ()),
            ),
            metadata={
                "matched_binding_count": len(bindings),
                "spring_boot_version": version_text,
                "spring_boot_major": boot_version.major if boot_version is not None else None,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class UnsupportedSpringBootVersionRule:
    """Flags Spring Boot 2.x lines as unsupported for modernization planning."""

    def id(self) -> str:
        return "codestrata-rule-unsupported-spring-boot-version"

    def name(self) -> str:
        return "Unsupported Spring Boot version"

    def description(self) -> str:
        return "Flags extracted Spring Boot 2.x versions as unsupported major lines."

    def supported_languages(self) -> frozenset[str]:
        return _JAVA

    def evaluate(self, context: RuleContext) -> RuleResult:
        boot_version = context.spring_boot_version()
        if boot_version is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no Spring Boot version extracted",
            )
        if not boot_version.is_spring_boot_2():
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Unsupported Spring Boot {boot_version.raw}",
            description=(
                f"Spring Boot {boot_version.raw} is on the 2.x major line, which is "
                "treated as unsupported for modernization planning."
            ),
            severity=FindingSeverity.HIGH,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:maven:spring-boot",
                    excerpt=f"spring-boot={boot_version.raw}",
                ),
            ),
            subject_keys=("spring-boot", boot_version.raw, "unsupported-2x"),
            metadata={
                "spring_boot_version": boot_version.raw,
                "spring_boot_major": boot_version.major,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class NodeEngineDetectedRule:
    def id(self) -> str:
        return "codestrata-rule-node-engine-detected"

    def name(self) -> str:
        return "Node engine detected"

    def description(self) -> str:
        return "Reports package.json engines.node constraints when present."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if not context.has_npm_project():
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="not an npm project",
            )
        engine = context.node_engine_version()
        if engine is None:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Node engine {engine.raw} declared",
            description=(f"package.json declares engines.node as {engine.raw}."),
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:nodejs:nodejs",
                    path="package.json",
                    excerpt=f"engines.node={engine.raw}",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "engines.node", engine.raw),
            metadata={"node_engine": engine.raw, "node_major": engine.major},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class MissingNodeEngineRule:
    def id(self) -> str:
        return "codestrata-rule-missing-node-engine"

    def name(self) -> str:
        return "Missing Node engine"

    def description(self) -> str:
        return "Flags npm projects that do not declare engines.node."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if not context.has_npm_project():
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="not an npm project",
            )
        if context.node_engine_version() is not None:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Missing Node engine declaration",
            description=(
                "package.json is present, but engines.node was not found in the "
                "extracted dependency graph."
            ),
            severity=FindingSeverity.LOW,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    path="package.json",
                    excerpt="package.json without engines.node",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "engines.node-missing"),
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class NpmLockfileMissingRule:
    def id(self) -> str:
        return "codestrata-rule-npm-lockfile-missing"

    def name(self) -> str:
        return "NPM lockfile missing"

    def description(self) -> str:
        return "Flags npm projects that do not include a lockfile."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if not context.has_npm_project():
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="not an npm project",
            )
        if context.has_basename(
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        ):
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="NPM lockfile missing",
            description=(
                "package.json is present, but no npm/yarn/pnpm lockfile was found "
                "in the repository inventory."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    path="package.json",
                    excerpt="package.json without lockfile",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "npm-lockfile"),
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class MissingCiWorkflowRule:
    def id(self) -> str:
        return "codestrata-rule-missing-ci-workflow"

    def name(self) -> str:
        return "Missing CI workflow"

    def description(self) -> str:
        return "Flags repositories without a detected GitHub Actions workflow directory."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        if context.path_contains(".github/workflows/"):
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title="Missing CI workflow",
            description=("No GitHub Actions workflow paths were found under .github/workflows/."),
            severity=FindingSeverity.LOW,
            category=FindingCategory.BUILD,
            evidence=(
                _evidence(
                    evidence_type="repository_manifest",
                    source_id=context.manifest.identity.repository_key,
                    excerpt="no paths under .github/workflows/",
                ),
            ),
            subject_keys=(context.manifest.identity.repository_key, "ci"),
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


def builtin_rules() -> tuple[Rule, ...]:
    """Return the ordered builtin rule set."""

    return (
        MissingReadmeRule(),
        MissingLicenseRule(),
        MissingTestsRule(),
        LargeRepositoryRule(),
        MavenWrapperMissingRule(),
        JavaDetectedRule(),
        SpringBootDetectedRule(),
        UnsupportedSpringBootVersionRule(),
        NodeEngineDetectedRule(),
        MissingNodeEngineRule(),
        NpmLockfileMissingRule(),
        MissingCiWorkflowRule(),
    )
