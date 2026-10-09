"""Map actual parser outputs onto inventory facts. Unsupported stays declared."""

from __future__ import annotations

from codestrata.application.evidence.inventory.models import ParserFactMapping, SupportKind

PARSER_FACT_MAPPINGS: tuple[ParserFactMapping, ...] = (
    ParserFactMapping(
        extractor_id="services.inventory.language.FilenameLanguageDetector",
        parser_output="language_label",
        fact_kind="language.detection",
        support=SupportKind.DETECTION_ONLY,
        limitations="Path/extension only; not structural support.",
    ),
    ParserFactMapping(
        extractor_id="services.detectors.java_technology_detector.JavaTechnologyDetector",
        parser_output="Technology(name, category, source)",
        fact_kind="technology.detection",
        support=SupportKind.DETECTION_ONLY,
        limitations="Spring Boot / Maven presence from pom.xml text; not AST.",
    ),
    ParserFactMapping(
        extractor_id="services.detectors.javascript_technology_detector.JavaScriptTechnologyDetector",
        parser_output="Technology(name, category, source)",
        fact_kind="technology.detection",
        support=SupportKind.DETECTION_ONLY,
        limitations="package.json engines/deps detected; no npm lock resolution.",
    ),
    ParserFactMapping(
        extractor_id="services.detectors.rust_technology_detector.RustTechnologyDetector",
        parser_output="Technology(name, category, source)",
        fact_kind="technology.detection",
        support=SupportKind.DETECTION_ONLY,
        limitations="Cargo.toml crate names only; no rustc AST or crate graph.",
    ),
    ParserFactMapping(
        extractor_id="language.java.core",
        parser_output="RawPackageFacts.package_files",
        fact_kind="source.files",
        support=SupportKind.STRUCTURAL,
    ),
    ParserFactMapping(
        extractor_id="language.java.core",
        parser_output="RawPackageFacts.resolved_edges",
        fact_kind="dependencies.imports",
        support=SupportKind.STRUCTURAL,
    ),
    ParserFactMapping(
        extractor_id="language.java.core",
        parser_output="RawPackageFacts.framework_hits",
        fact_kind="framework.usage",
        support=SupportKind.STRUCTURAL,
        limitations="Spring/JPA annotation patterns only.",
    ),
    ParserFactMapping(
        extractor_id="language.javascript.core",
        parser_output="RawPackageFacts.resolved_edges",
        fact_kind="dependencies.imports",
        support=SupportKind.STRUCTURAL,
        limitations="Type-only imports partial; no workspace graph.",
    ),
    ParserFactMapping(
        extractor_id="language.javascript.core",
        parser_output="RawPackageFacts.framework_hits",
        fact_kind="framework.usage",
        support=SupportKind.STRUCTURAL,
        limitations=(
            "Domain-layer decorator and quoted import patterns only, "
            "no module graph and no component tree."
        ),
    ),
    ParserFactMapping(
        extractor_id="language.python.core",
        parser_output="RawPackageFacts.resolved_kinds[type_only]",
        fact_kind="dependencies.type-only",
        support=SupportKind.STRUCTURAL,
    ),
    ParserFactMapping(
        extractor_id="language.php.core",
        parser_output="RawPackageFacts.resolved_edges",
        fact_kind="dependencies.imports",
        support=SupportKind.STRUCTURAL,
        limitations="use / require / include only.",
    ),
    ParserFactMapping(
        extractor_id="language.csharp.core",
        parser_output="RawPackageFacts.resolved_edges",
        fact_kind="dependencies.imports",
        support=SupportKind.STRUCTURAL,
        limitations="using / using static only; no Roslyn.",
    ),
    ParserFactMapping(
        extractor_id="language.java.complexity",
        parser_output="FileComplexityEvidence.branch_point_count",
        fact_kind="complexity.branches",
        support=SupportKind.STRUCTURAL,
        limitations="Brace-aware regex; lambdas unmeasured.",
    ),
    ParserFactMapping(
        extractor_id="language.javascript.complexity",
        parser_output="FileComplexityEvidence.branch_point_count",
        fact_kind="complexity.branches",
        support=SupportKind.STRUCTURAL,
        limitations=(
            "Brace-aware scan of functions, methods, and assigned arrows. "
            "Not the TypeScript compiler."
        ),
    ),
    ParserFactMapping(
        extractor_id="dependency.maven.manifest",
        parser_output="DependencyDeclarationEvidence.normalized_identity",
        fact_kind="dependency.declared_coordinate",
        support=SupportKind.STRUCTURAL,
        limitations="Local property resolution only; no Maven lockfile collector.",
    ),
    ParserFactMapping(
        extractor_id="inventory.npm.v1",
        parser_output="NpmDeclarationRecord / NpmResolutionRecord",
        fact_kind="dependency.declared_coordinate",
        support=SupportKind.STRUCTURAL,
        limitations=(
            "Declaration IDs are the coverage unit; lock occurrences are "
            "separate. Missing lock is UNKNOWN, not zero dependencies."
        ),
    ),
    ParserFactMapping(
        extractor_id="inventory.m04.v1",
        parser_output="SurfaceDeclarationFact",
        fact_kind="api.config.surface",
        support=SupportKind.STRUCTURAL,
        limitations=(
            "Literal Spring/Flask/FastAPI/Express/ASP.NET routes. Dynamic "
            "routing and unsupported frameworks stay UNKNOWN."
        ),
    ),
    ParserFactMapping(
        extractor_id="inventory.facts.e05.2",
        parser_output="InventoryFactBundle",
        fact_kind="inventory.fact",
        support=SupportKind.STRUCTURAL,
        limitations=(
            "Uses Repository Graph IDs. E05.3 Engine-local envelope/projections "
            "are the consumer contract; E01.2 shared envelopes are not claimed."
        ),
    ),
    ParserFactMapping(
        extractor_id="dependency.composer.manifest",
        parser_output="DependencyDeclarationEvidence",
        fact_kind="dependency.declared_coordinate",
        support=SupportKind.STRUCTURAL,
        limitations="composer.lock is not parsed; resolution remains UNKNOWN.",
    ),
    ParserFactMapping(
        extractor_id="dependency.nuget.manifest",
        parser_output="DependencyDeclarationEvidence",
        fact_kind="dependency.declared_coordinate",
        support=SupportKind.STRUCTURAL,
        limitations="packages.lock.json is skipped; declaration-only tier.",
    ),
    ParserFactMapping(
        extractor_id="analyzers.github_actions_parser.GitHubActionsParser",
        parser_output="CicdPipeline.jobs / build_commands / metadata.commands",
        fact_kind="ci.invocation",
        support=SupportKind.STRUCTURAL,
        limitations="Observed configuration, not that the job ran.",
    ),
    ParserFactMapping(
        extractor_id="analyzers.cicd_discovery_analyzer.CicdDiscoveryAnalyzer",
        parser_output="CicdPipeline.provider for non-GitHub files",
        fact_kind="ci.detection",
        support=SupportKind.DETECTION_ONLY,
        limitations="GitLab/Jenkins/Azure/CircleCI/Travis/Bitbucket/CodeBuild are path detection.",
    ),
)
