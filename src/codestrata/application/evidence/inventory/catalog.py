"""Combined extractor depth pin built from live providers plus inspected collectors."""

from __future__ import annotations

from codestrata.application.evidence.dependency.paths import classify_manifest_basename
from codestrata.application.evidence.inventory.fact_map import PARSER_FACT_MAPPINGS
from codestrata.application.evidence.inventory.models import (
    EXTRACTOR_DEPTH_PIN_VERSION,
    CiDepthPin,
    ExtractorDepthPin,
    ManifestDepthPin,
    ResolutionObservation,
    SupportKind,
)
from codestrata.application.evidence.language.factory import create_language_evidence_registry
from codestrata.application.evidence.language.providers.depth import (
    LANGUAGE_SUPPORT_PINS,
    pin_by_provider_id,
)

DETECTION_ONLY_LANGUAGES: tuple[str, ...] = (
    "C",
    "C++",
    "CMake",
    "Dockerfile",
    "Go",
    "HTML",
    "JSON",
    "Kotlin",
    "Makefile",
    "Ruby",
    "Rust",
    "Scala",
    "Shell",
    "Swift",
    "YAML",
)

MANIFEST_DEPTH_PINS: tuple[ManifestDepthPin, ...] = (
    ManifestDepthPin(
        ecosystem="maven",
        detection_basenames=("pom.xml",),
        lockfile_basenames=(),
        structural_collector=("codestrata.application.evidence.dependency.maven_collector"),
        structural_provider_id="dependency.maven.manifest",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.DECLARED_ONLY,
        limitations="Property resolution is local; missing lock is N/A, not zero deps.",
    ),
    ManifestDepthPin(
        ecosystem="gradle",
        detection_basenames=("build.gradle", "build.gradle.kts"),
        lockfile_basenames=("gradle.lockfile",),
        structural_collector=("codestrata.application.evidence.dependency.gradle_collector"),
        structural_provider_id="dependency.gradle.manifest",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.DECLARED_ONLY,
        limitations="Lockfile is detected; collector is declaration-tier.",
    ),
    ManifestDepthPin(
        ecosystem="python",
        detection_basenames=("pyproject.toml", "requirements.txt", "Pipfile"),
        lockfile_basenames=("poetry.lock", "Pipfile.lock", "uv.lock"),
        structural_collector=("codestrata.application.evidence.dependency.python_collector"),
        structural_provider_id="dependency.python.manifest",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.DECLARED_ONLY,
        limitations="Lockfiles may be detected without resolved package identities.",
    ),
    ManifestDepthPin(
        ecosystem="npm",
        detection_basenames=("package.json",),
        lockfile_basenames=(
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        ),
        structural_collector="codestrata.application.evidence.inventory.npm",
        structural_provider_id="inventory.npm.v1",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.UNKNOWN,
        limitations=(
            "package.json declarations and package-lock.json occurrences. "
            "Missing lock is UNKNOWN, not zero dependencies. yarn.lock and "
            "pnpm-lock.yaml remain unparsed. Not in DependencyEcosystem."
        ),
    ),
    ManifestDepthPin(
        ecosystem="composer",
        detection_basenames=("composer.json",),
        lockfile_basenames=("composer.lock",),
        structural_collector=("codestrata.application.evidence.dependency.composer_collector"),
        structural_provider_id="dependency.composer.manifest",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.UNKNOWN,
        limitations="Lower tier: composer.lock is not parsed.",
    ),
    ManifestDepthPin(
        ecosystem="nuget",
        detection_basenames=("packages.config", "Directory.Packages.props", "*.csproj"),
        lockfile_basenames=("packages.lock.json",),
        structural_collector=("codestrata.application.evidence.dependency.nuget_collector"),
        structural_provider_id="dependency.nuget.manifest",
        support=SupportKind.STRUCTURAL,
        resolution=ResolutionObservation.UNKNOWN,
        limitations="Lower tier: packages.lock.json is skipped by the collector.",
    ),
    ManifestDepthPin(
        ecosystem="go",
        detection_basenames=("go.mod",),
        lockfile_basenames=("go.sum",),
        support=SupportKind.DETECTION_ONLY,
        resolution=ResolutionObservation.UNKNOWN,
        limitations="No Go structural dependency collector.",
    ),
    ManifestDepthPin(
        ecosystem="cargo",
        detection_basenames=("Cargo.toml",),
        lockfile_basenames=("Cargo.lock",),
        support=SupportKind.DETECTION_ONLY,
        resolution=ResolutionObservation.UNKNOWN,
        limitations="No Cargo structural dependency collector.",
    ),
)

CI_DEPTH_PINS: tuple[CiDepthPin, ...] = (
    CiDepthPin(
        provider="github-actions",
        detection_paths=(".github/workflows/*.yml", ".github/workflows/*.yaml"),
        support=SupportKind.STRUCTURAL,
        parser="codestrata.services.analyzers.github_actions_parser.GitHubActionsParser",
        limitations="Literal run/uses recorded; ${{ }} and npm run are unresolved.",
    ),
    CiDepthPin(
        provider="gitlab-ci",
        detection_paths=(".gitlab-ci.yml", ".gitlab-ci.yaml"),
        support=SupportKind.DETECTION_ONLY,
        limitations="Path detection only.",
    ),
    CiDepthPin(
        provider="jenkins",
        detection_paths=("Jenkinsfile",),
        support=SupportKind.DETECTION_ONLY,
    ),
    CiDepthPin(
        provider="azure-devops",
        detection_paths=("azure-pipelines.yml", "azure-pipelines.yaml"),
        support=SupportKind.DETECTION_ONLY,
    ),
    CiDepthPin(
        provider="circleci",
        detection_paths=(".circleci/config.yml", ".circleci/config.yaml"),
        support=SupportKind.DETECTION_ONLY,
    ),
    CiDepthPin(
        provider="travis-ci",
        detection_paths=(".travis.yml", ".travis.yaml"),
        support=SupportKind.DETECTION_ONLY,
    ),
    CiDepthPin(
        provider="bitbucket-pipelines",
        detection_paths=("bitbucket-pipelines.yml", "bitbucket-pipelines.yaml"),
        support=SupportKind.DETECTION_ONLY,
    ),
    CiDepthPin(
        provider="aws-codebuild",
        detection_paths=("buildspec.yml", "buildspec.yaml"),
        support=SupportKind.DETECTION_ONLY,
    ),
)


def build_extractor_depth_pin() -> ExtractorDepthPin:
    """Pin from live language providers plus inspected manifest/CI extractors."""

    registry = create_language_evidence_registry()
    pins = pin_by_provider_id()
    for provider in registry.providers():
        pin = pins.get(str(provider.metadata.provider_id))
        if pin is None:
            raise RuntimeError(f"unpinned language provider {provider.metadata.provider_id}")
        if tuple(provider.metadata.supported_languages) != (pin.language,):
            raise RuntimeError(
                f"language pin drift for {pin.provider_id}: "
                f"{provider.metadata.supported_languages!r} vs {(pin.language,)!r}"
            )
        if str(provider.metadata.provider_version) != pin.provider_version:
            raise RuntimeError(f"version pin drift for {pin.provider_id}")
        if frozenset(provider.metadata.supported_file_extensions) != frozenset(
            pin.detection_suffixes
        ):
            raise RuntimeError(f"suffix pin drift for {pin.provider_id}")
    from codestrata.services.analyzers.dependency_discovery_analyzer import (
        DependencyDiscoveryAnalyzer,
    )

    if "pom.xml" not in DependencyDiscoveryAnalyzer.MANIFESTS:
        raise RuntimeError("maven detection basename missing from discovery analyzer")
    if classify_manifest_basename("pom.xml") is None:
        raise RuntimeError("maven structural classifier does not recognize pom.xml")
    if classify_manifest_basename("package.json") is not None:
        raise RuntimeError("npm must stay outside DependencyEcosystem; inventory.npm collects it")
    return ExtractorDepthPin(
        version=EXTRACTOR_DEPTH_PIN_VERSION,
        languages=tuple(pin.language for pin in LANGUAGE_SUPPORT_PINS),
        manifests=MANIFEST_DEPTH_PINS,
        ci=CI_DEPTH_PINS,
        fact_mappings=PARSER_FACT_MAPPINGS,
        detection_only_languages=DETECTION_ONLY_LANGUAGES,
        notes=(
            "detection_count_is_not_structural_support",
            "javascript_includes_typescript_suffixes",
            "javascript_complexity_is_structural_scan",
            "npm_inventory_collector_is_structural",
            "npm_is_outside_dependency_ecosystem_enum",
            "composer_nuget_are_declaration_tiers",
            "early_discovery_does_not_require_yaml_runtime",
            "no_install_or_script_execution",
        ),
    )
