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


class AngularDetectedRule:
    """Reports Angular framework presence and extracted version."""

    def id(self) -> str:
        return "codestrata-rule-angular-detected"

    def name(self) -> str:
        return "Angular detected"

    def description(self) -> str:
        return "Reports Angular framework presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("angular")
        angular_ver = context.angular_version()
        has_angular_json = context.has_basename("angular.json")
        if not bindings and angular_ver is None and not has_angular_json:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        version_text = angular_ver.raw if angular_ver is not None else None
        if version_text is not None:
            title = f"Angular {version_text} detected"
            description = f"Angular is present at version {version_text}."
        else:
            title = "Angular detected"
            description = (
                "Angular framework artifacts or dependencies were detected in repository inventory."
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
                                source_id="dependency:npm:@angular/core",
                                excerpt=f"@angular/core={version_text}",
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
                "angular",
                *(binding.binding_id for binding in bindings),
                *(("angular-version", version_text) if version_text is not None else ()),
            ),
            metadata={
                "matched_binding_count": len(bindings),
                "angular_version": version_text,
                "angular_major": angular_ver.major if angular_ver is not None else None,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class UnsupportedAngularVersionRule:
    """Flags legacy AngularJS or EOL Angular versions (< 16)."""

    def id(self) -> str:
        return "codestrata-rule-unsupported-angular-version"

    def name(self) -> str:
        return "Unsupported Angular version"

    def description(self) -> str:
        return "Flags legacy AngularJS 1.x or end-of-life Angular versions (< 16)."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        angular_ver = context.angular_version()
        if angular_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no Angular version extracted",
            )
        major = angular_ver.major
        if major is None or major >= 16:
            return RuleResult(rule_id=self.id(), findings=())
        is_angularjs = major == 1
        title = (
            f"Legacy AngularJS {angular_ver.raw} detected"
            if is_angularjs
            else f"Unsupported Angular {angular_ver.raw}"
        )
        description = (
            f"AngularJS {angular_ver.raw} reached End-of-Life and is completely unsupported."
            if is_angularjs
            else (
                f"Angular {angular_ver.raw} is on a deprecated major line (< 16) "
                "that has reached End-of-Life."
            )
        )
        finding = Finding.create(
            rule_id=self.id(),
            title=title,
            description=description,
            severity=FindingSeverity.HIGH,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:@angular/core",
                    excerpt=f"angular={angular_ver.raw}",
                ),
            ),
            subject_keys=("angular", angular_ver.raw, "unsupported-angular"),
            metadata={
                "angular_version": angular_ver.raw,
                "angular_major": major,
                "is_angularjs": is_angularjs,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class ReactDetectedRule:
    """Reports React presence and declared version."""

    def id(self) -> str:
        return "codestrata-rule-react-detected"

    def name(self) -> str:
        return "React detected"

    def description(self) -> str:
        return "Reports React library presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("react")
        react_ver = context.react_version()
        if not bindings and react_ver is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        version_text = react_ver.raw if react_ver is not None else None
        if version_text is not None:
            title = f"React {version_text} detected"
            description = f"React is present at version {version_text}."
        else:
            title = "React detected"
            description = "React dependencies or bindings were detected in repository inventory."
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
                                source_id="dependency:npm:react",
                                excerpt=f"react={version_text}",
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
                "react",
                *(binding.binding_id for binding in bindings),
                *(("react-version", version_text) if version_text is not None else ()),
            ),
            metadata={
                "matched_binding_count": len(bindings),
                "react_version": version_text,
                "react_major": react_ver.major if react_ver is not None else None,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class OutdatedReactVersionRule:
    """Flags React versions prior to React 18."""

    def id(self) -> str:
        return "codestrata-rule-outdated-react-version"

    def name(self) -> str:
        return "Outdated React version"

    def description(self) -> str:
        return "Flags React versions prior to React 18 as lacking modern concurrent features."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        react_ver = context.react_version()
        if react_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no React version extracted",
            )
        major = react_ver.major
        if major is None or major >= 18:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Outdated React {react_ver.raw}",
            description=(
                f"React {react_ver.raw} is prior to React 18 and lacks concurrent rendering, "
                "automatic batching, and modern React Server Component architecture."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:react",
                    excerpt=f"react={react_ver.raw}",
                ),
            ),
            subject_keys=("react", react_ver.raw, "outdated-react"),
            metadata={
                "react_version": react_ver.raw,
                "react_major": major,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class VueDetectedRule:
    """Reports Vue.js framework presence and declared version."""

    def id(self) -> str:
        return "codestrata-rule-vue-detected"

    def name(self) -> str:
        return "Vue.js detected"

    def description(self) -> str:
        return "Reports Vue.js framework presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("vue")
        vue_ver = context.vue_version()
        if not bindings and vue_ver is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        version_text = vue_ver.raw if vue_ver is not None else None
        if version_text is not None:
            title = f"Vue.js {version_text} detected"
            description = f"Vue.js is present at version {version_text}."
        else:
            title = "Vue.js detected"
            description = "Vue.js dependencies or bindings were detected in repository inventory."
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
                                source_id="dependency:npm:vue",
                                excerpt=f"vue={version_text}",
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
                "vue",
                *(binding.binding_id for binding in bindings),
                *(("vue-version", version_text) if version_text is not None else ()),
            ),
            metadata={
                "matched_binding_count": len(bindings),
                "vue_version": version_text,
                "vue_major": vue_ver.major if vue_ver is not None else None,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class UnsupportedVueVersionRule:
    """Flags Vue 2.x which reached End-of-Life on December 31, 2023."""

    def id(self) -> str:
        return "codestrata-rule-unsupported-vue-version"

    def name(self) -> str:
        return "Unsupported Vue 2 version"

    def description(self) -> str:
        return "Flags Vue 2 versions as end-of-life (EOL as of Dec 31, 2023)."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        vue_ver = context.vue_version()
        if vue_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no Vue version extracted",
            )
        major = vue_ver.major
        if major != 2:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Unsupported Vue 2 ({vue_ver.raw})",
            description=(
                f"Vue {vue_ver.raw} reached official End-of-Life on December 31, 2023 "
                "and no longer receives official security patches or updates. Modernize to Vue 3."
            ),
            severity=FindingSeverity.HIGH,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:vue",
                    excerpt=f"vue={vue_ver.raw}",
                ),
            ),
            subject_keys=("vue", vue_ver.raw, "unsupported-vue2"),
            metadata={
                "vue_version": vue_ver.raw,
                "vue_major": major,
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class NextJsDetectedRule:
    """Reports Next.js framework presence and extracted version."""

    def id(self) -> str:
        return "codestrata-rule-nextjs-detected"

    def name(self) -> str:
        return "Next.js detected"

    def description(self) -> str:
        return "Reports Next.js framework presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("next")
        next_ver = context.nextjs_version()
        if not bindings and next_ver is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        ver_text = f" (version {next_ver.raw})" if next_ver is not None else ""
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Next.js framework detected{ver_text}",
            description=(
                f"Next.js framework identified in repository{ver_text}. "
                "Next.js provides hybrid static and server rendering and TypeScript support."
            ),
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.MODERNIZATION,
            affected_assessment_node_ids=tuple(
                sorted(
                    {node.root: node for node in affected}.values(),
                    key=lambda node: node.root,
                )
            ),
            evidence=(
                _evidence(
                    evidence_type="framework_manifest",
                    source_id="dependency:npm:next",
                    excerpt=f"next{ver_text}",
                ),
            ),
            subject_keys=("next", "framework", next_ver.raw if next_ver else "detected"),
            metadata={
                "nextjs_version": next_ver.raw if next_ver else None,
                "framework": "next",
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class OutdatedNextJsVersionRule:
    """Flags Next.js versions older than 13.x (legacy Pages router only)."""

    def id(self) -> str:
        return "codestrata-rule-outdated-nextjs-version"

    def name(self) -> str:
        return "Outdated Next.js version (<13)"

    def description(self) -> str:
        return "Flags Next.js versions older than 13 as lacking App Router and Server Components."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        next_ver = context.nextjs_version()
        if next_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no Next.js version extracted",
            )
        major = next_ver.major
        if major is None or major >= 13:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Outdated Next.js version ({next_ver.raw})",
            description=(
                f"Next.js {next_ver.raw} predates Next.js 13 and lacks the App Router, "
                "Server Components, and modern performance optimizations. Upgrade to Next.js 14+."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:next",
                    excerpt=f"next={next_ver.raw}",
                ),
            ),
            subject_keys=("next", next_ver.raw, "outdated-nextjs"),
            metadata={"nextjs_version": next_ver.raw, "nextjs_major": major},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class NestJsDetectedRule:
    """Reports NestJS backend framework presence and extracted version."""

    def id(self) -> str:
        return "codestrata-rule-nestjs-detected"

    def name(self) -> str:
        return "NestJS detected"

    def description(self) -> str:
        return "Reports NestJS framework presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("nestjs")
        nest_ver = context.nestjs_version()
        if not bindings and nest_ver is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        ver_text = f" (version {nest_ver.raw})" if nest_ver is not None else ""
        finding = Finding.create(
            rule_id=self.id(),
            title=f"NestJS framework detected{ver_text}",
            description=(
                f"NestJS framework identified in repository{ver_text}. "
                "NestJS provides modular architecture, TypeScript decorators, "
                "and dependency injection."
            ),
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.MODERNIZATION,
            affected_assessment_node_ids=tuple(
                sorted(
                    {node.root: node for node in affected}.values(),
                    key=lambda node: node.root,
                )
            ),
            evidence=(
                _evidence(
                    evidence_type="framework_manifest",
                    source_id="dependency:npm:@nestjs/core",
                    excerpt=f"@nestjs/core{ver_text}",
                ),
            ),
            subject_keys=("nestjs", "framework", nest_ver.raw if nest_ver else "detected"),
            metadata={
                "nestjs_version": nest_ver.raw if nest_ver else None,
                "framework": "nestjs",
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class OutdatedNestJsVersionRule:
    """Flags NestJS versions older than 9.x."""

    def id(self) -> str:
        return "codestrata-rule-outdated-nestjs-version"

    def name(self) -> str:
        return "Outdated NestJS version (<9)"

    def description(self) -> str:
        return "Flags NestJS versions older than 9 as legacy/outdated."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        nest_ver = context.nestjs_version()
        if nest_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no NestJS version extracted",
            )
        major = nest_ver.major
        if major is None or major >= 9:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Outdated NestJS version ({nest_ver.raw})",
            description=(
                f"NestJS {nest_ver.raw} is older than NestJS 9 and lacks modern Node LTS "
                "compatibility. Upgrade to NestJS 10 or newer."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:@nestjs/core",
                    excerpt=f"@nestjs/core={nest_ver.raw}",
                ),
            ),
            subject_keys=("nestjs", nest_ver.raw, "outdated-nestjs"),
            metadata={"nestjs_version": nest_ver.raw, "nestjs_major": major},
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class SvelteDetectedRule:
    """Reports Svelte framework presence and extracted version."""

    def id(self) -> str:
        return "codestrata-rule-svelte-detected"

    def name(self) -> str:
        return "Svelte detected"

    def description(self) -> str:
        return "Reports Svelte framework presence and declared version."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        bindings = context.bindings_for_key("svelte")
        svelte_ver = context.svelte_version()
        if not bindings and svelte_ver is None:
            return RuleResult(rule_id=self.id(), findings=())
        affected: list[NodeId] = []
        for binding in bindings:
            affected.extend(context.assessment_nodes_for_binding(binding))
        ver_text = f" (version {svelte_ver.raw})" if svelte_ver is not None else ""
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Svelte framework detected{ver_text}",
            description=(
                f"Svelte framework identified in repository{ver_text}. "
                "Svelte compiles components into efficient imperative JavaScript."
            ),
            severity=FindingSeverity.INFORMATIONAL,
            category=FindingCategory.MODERNIZATION,
            affected_assessment_node_ids=tuple(
                sorted(
                    {node.root: node for node in affected}.values(),
                    key=lambda node: node.root,
                )
            ),
            evidence=(
                _evidence(
                    evidence_type="framework_manifest",
                    source_id="dependency:npm:svelte",
                    excerpt=f"svelte{ver_text}",
                ),
            ),
            subject_keys=("svelte", "framework", svelte_ver.raw if svelte_ver else "detected"),
            metadata={
                "svelte_version": svelte_ver.raw if svelte_ver else None,
                "framework": "svelte",
            },
        )
        return RuleResult(rule_id=self.id(), findings=(finding,))


class OutdatedSvelteVersionRule:
    """Flags Svelte versions older than 4.x."""

    def id(self) -> str:
        return "codestrata-rule-outdated-svelte-version"

    def name(self) -> str:
        return "Outdated Svelte version (<4)"

    def description(self) -> str:
        return "Flags Svelte versions older than 4 as legacy."

    def supported_languages(self) -> frozenset[str]:
        return _ALL_LANGUAGES

    def evaluate(self, context: RuleContext) -> RuleResult:
        svelte_ver = context.svelte_version()
        if svelte_ver is None:
            return RuleResult(
                rule_id=self.id(),
                findings=(),
                skipped=True,
                skip_reason="no Svelte version extracted",
            )
        major = svelte_ver.major
        if major is None or major >= 4:
            return RuleResult(rule_id=self.id(), findings=())
        finding = Finding.create(
            rule_id=self.id(),
            title=f"Outdated Svelte version ({svelte_ver.raw})",
            description=(
                f"Svelte {svelte_ver.raw} is older than Svelte 4 and does not support modern "
                "runes or SvelteKit 2. Upgrade to Svelte 4 or 5."
            ),
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.DEPENDENCY,
            evidence=(
                _evidence(
                    evidence_type="dependency_version",
                    source_id="dependency:npm:svelte",
                    excerpt=f"svelte={svelte_ver.raw}",
                ),
            ),
            subject_keys=("svelte", svelte_ver.raw, "outdated-svelte"),
            metadata={"svelte_version": svelte_ver.raw, "svelte_major": major},
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
        AngularDetectedRule(),
        UnsupportedAngularVersionRule(),
        ReactDetectedRule(),
        OutdatedReactVersionRule(),
        VueDetectedRule(),
        UnsupportedVueVersionRule(),
        NextJsDetectedRule(),
        OutdatedNextJsVersionRule(),
        NestJsDetectedRule(),
        OutdatedNestJsVersionRule(),
        SvelteDetectedRule(),
        OutdatedSvelteVersionRule(),
    )
