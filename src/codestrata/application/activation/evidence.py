"""Collect repository evidence signals for pack activation (existing facts only)."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.models import AnalysisResult

_TD_LANGUAGES = frozenset(
    {
        "java",
        "javascript",
        "typescript",
        "python",
        "php",
        "c#",
        "csharp",
        "kotlin",
    }
)

_AI_FRAMEWORK_MARKERS = frozenset(
    {
        "langchain",
        "llama",
        "llamaindex",
        "openai",
        "anthropic",
        "huggingface",
        "transformers",
        "tensorflow",
        "pytorch",
        "torch",
        "bedrock",
        "sagemaker",
        "ollama",
        "mlx",
        "keras",
        "scikit-learn",
        "sklearn",
        "spacy",
        "onnx",
    }
)


@dataclass(frozen=True, slots=True)
class RepositoryEvidenceSignals:
    """Normalized activation inputs derived from AnalysisResult."""

    languages: tuple[str, ...]
    dependency_evidence: tuple[str, ...]
    architecture_evidence: tuple[str, ...]
    technical_debt_evidence: tuple[str, ...]
    testing_evidence: tuple[str, ...]
    cloud_evidence: tuple[str, ...]
    ai_readiness_evidence: tuple[str, ...]

    @property
    def has_dependency_manifests(self) -> bool:
        return bool(self.dependency_evidence)

    @property
    def has_architecture_structure(self) -> bool:
        return bool(self.architecture_evidence)

    @property
    def has_td_eligible_language(self) -> bool:
        return bool(self.technical_debt_evidence)

    @property
    def has_tests(self) -> bool:
        return bool(self.testing_evidence)

    @property
    def has_cloud(self) -> bool:
        return bool(self.cloud_evidence)

    @property
    def has_ai_frameworks(self) -> bool:
        return bool(self.ai_readiness_evidence)


def collect_repository_evidence(analysis: AnalysisResult) -> RepositoryEvidenceSignals:
    """Derive activation evidence from deterministic analysis facts only."""

    facts = analysis.facts
    languages = _languages(analysis)
    return RepositoryEvidenceSignals(
        languages=languages,
        dependency_evidence=_dependency_evidence(facts, analysis),
        architecture_evidence=_architecture_evidence(facts, languages),
        technical_debt_evidence=_technical_debt_evidence(languages),
        testing_evidence=_testing_evidence(facts, analysis),
        cloud_evidence=_cloud_evidence(facts),
        ai_readiness_evidence=_ai_readiness_evidence(analysis, facts),
    )


def _languages(analysis: AnalysisResult) -> tuple[str, ...]:
    names: list[str] = []
    tech_facts = analysis.facts.technology if analysis.facts is not None else None
    if tech_facts is not None:
        names.extend(tech_facts.programming_languages)
        names.extend(tech_facts.detected_technologies)
    for item in analysis.technologies:
        names.append(item.name)
        if item.category is not None and str(item.category).lower() == "language":
            names.append(item.name)
    normalized = sorted({_norm(name) for name in names if name and name.strip()})
    return tuple(normalized)


def _dependency_evidence(facts: object, analysis: AnalysisResult) -> tuple[str, ...]:
    evidence: list[str] = []
    deps = getattr(getattr(facts, "dependencies", None), "manifests", None)
    if deps:
        for manifest in deps:
            path = getattr(manifest, "path", None) or "manifest"
            ecosystem = getattr(manifest, "ecosystem", None) or "unknown"
            evidence.append(f"manifest:{ecosystem}:{path}")
    build = getattr(facts, "build", None)
    if build is not None:
        for path in getattr(build, "build_files", ()) or ():
            evidence.append(f"build_file:{path}")
        for path in getattr(build, "lock_files", ()) or ():
            evidence.append(f"lock_file:{path}")
        for system in getattr(build, "build_systems", ()) or ():
            evidence.append(f"build_system:{system}")
    # Fall back to known inventory filenames when facts are sparse.
    for path in analysis.repository.files:
        lower = str(path).replace("\\", "/").lower()
        base = lower.rsplit("/", 1)[-1]
        if base in {
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "requirements.txt",
            "pyproject.toml",
            "poetry.lock",
            "go.mod",
            "cargo.toml",
            "composer.json",
        }:
            evidence.append(f"inventory:{path}")
    return tuple(sorted(dict.fromkeys(evidence)))


def _architecture_evidence(facts: object, languages: tuple[str, ...]) -> tuple[str, ...]:
    evidence: list[str] = []
    build = getattr(facts, "build", None)
    if build is not None and bool(getattr(build, "multi_module", False)):
        evidence.append("build:multi_module")
        modules = getattr(build, "modules", None) or ()
        if modules:
            evidence.append(f"modules:{len(modules)}")
    structure = getattr(facts, "structure", None)
    if structure is not None:
        layers = getattr(structure, "architecture_layers", None) or ()
        for layer in layers:
            evidence.append(f"structure_layer:{layer}")
        source_count = getattr(structure, "source_file_count", None)
        if isinstance(source_count, int) and source_count >= 8:
            evidence.append(f"source_file_count:{source_count}")
        app_count = getattr(structure, "application_count", None)
        if isinstance(app_count, int) and app_count >= 2:
            evidence.append(f"application_count:{app_count}")
    architecture = getattr(facts, "architecture", None)
    if architecture is not None:
        for flag in (
            "has_api_layer",
            "has_service_layer",
            "has_persistence_layer",
            "has_domain_layer",
            "is_multi_application",
        ):
            if getattr(architecture, flag, None) is True:
                evidence.append(f"architecture:{flag}")
    structural_langs = sorted(
        lang for lang in languages if lang in {"java", "kotlin", "csharp", "c#", "python"}
    )
    if structural_langs and not evidence:
        # Enough signal to attempt architecture rules on common structured stacks.
        if any(lang in {"java", "kotlin", "csharp", "c#"} for lang in structural_langs):
            evidence.append("language_structure:" + ",".join(structural_langs))
    return tuple(sorted(dict.fromkeys(evidence)))


def _technical_debt_evidence(languages: tuple[str, ...]) -> tuple[str, ...]:
    matched = sorted(lang for lang in languages if lang in _TD_LANGUAGES)
    return tuple(f"td_language:{lang}" for lang in matched)


def _testing_evidence(facts: object, analysis: AnalysisResult) -> tuple[str, ...]:
    evidence: list[str] = []
    structure = getattr(facts, "structure", None)
    if structure is not None:
        if getattr(structure, "has_tests", None) is True:
            evidence.append("structure:has_tests")
        test_count = getattr(structure, "test_file_count", None)
        if isinstance(test_count, int) and test_count > 0:
            evidence.append(f"test_file_count:{test_count}")
    tech = getattr(facts, "technology", None)
    if tech is not None:
        for framework in getattr(tech, "test_frameworks", ()) or ():
            evidence.append(f"test_framework:{framework}")
    for path in analysis.repository.files:
        lower = str(path).replace("\\", "/").lower()
        if (
            "/test/" in f"/{lower}/"
            or "/tests/" in f"/{lower}/"
            or lower.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
            or lower.endswith("tests.java")
            or lower.endswith("_test.py")
            or lower.endswith("test.py")
        ):
            evidence.append(f"inventory_test:{path}")
            break
    return tuple(sorted(dict.fromkeys(evidence)))


def _cloud_evidence(facts: object) -> tuple[str, ...]:
    evidence: list[str] = []
    cloud = getattr(facts, "cloud", None)
    if cloud is None:
        return ()
    for flag in (
        "has_docker",
        "has_devcontainer",
        "has_docker_compose",
        "has_kubernetes",
        "has_helm",
        "has_terraform",
        "has_cloudformation",
        "has_serverless",
    ):
        if getattr(cloud, flag, None) is True:
            evidence.append(f"cloud:{flag}")
    for capability in getattr(cloud, "cloud_capabilities", ()) or ():
        evidence.append(f"cloud_capability:{capability}")
    return tuple(sorted(dict.fromkeys(evidence)))


def _ai_readiness_evidence(analysis: AnalysisResult, facts: object) -> tuple[str, ...]:
    evidence: list[str] = []
    candidates: list[str] = []
    tech = getattr(facts, "technology", None)
    if tech is not None:
        candidates.extend(getattr(tech, "frameworks", ()) or ())
        candidates.extend(getattr(tech, "detected_technologies", ()) or ())
        candidates.extend(getattr(tech, "programming_languages", ()) or ())
    for item in analysis.technologies:
        candidates.append(item.name)
    deps = getattr(facts, "dependencies", None)
    if deps is not None:
        for dependency in getattr(deps, "dependencies", ()) or ():
            candidates.append(getattr(dependency, "name", "") or "")
        candidates.extend(getattr(deps, "framework_dependencies", ()) or ())
    for name in candidates:
        marker = _norm(name)
        if not marker:
            continue
        for needle in _AI_FRAMEWORK_MARKERS:
            if needle in marker or marker in needle:
                evidence.append(f"ai_framework:{name}")
                break
    return tuple(sorted(dict.fromkeys(evidence)))


def _norm(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


__all__ = [
    "RepositoryEvidenceSignals",
    "collect_repository_evidence",
]
