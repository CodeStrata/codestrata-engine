"""Pinned detection vs structural depth for the five language providers.

E05.1 records what the existing extractors actually do. File detection and
technology-detector hits are not structural support. Complexity is a separate
capability: JS/TS uses a brace-aware scan, not the TypeScript compiler.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.contracts.enums import DepthTier
from codestrata.domain.evidence.language.capabilities import CapabilityMaturity


class LanguageSupportPin(BaseModel):
    """Declared depth for one language evidence provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    launch_tier: DepthTier
    provider_id: str
    provider_version: str
    detection_suffixes: tuple[str, ...]
    structural_maturity: CapabilityMaturity
    structural_parser: str
    complexity_provider_id: str | None = None
    complexity_maturity: CapabilityMaturity | None = None
    supported_frameworks: tuple[str, ...] = ()
    framework_structural: bool = False
    unsupported_syntax: tuple[str, ...] = ()
    unsupported_frameworks: tuple[str, ...] = ()
    limitations: str = ""
    notes: tuple[str, ...] = Field(default_factory=tuple)


JAVA_LANGUAGE_PIN = LanguageSupportPin(
    language="java",
    launch_tier=DepthTier.DEEPEST_TARGET,
    provider_id="language.java.core",
    provider_version="1.0.0",
    detection_suffixes=(".java",),
    structural_maturity=CapabilityMaturity.PARTIAL,
    structural_parser="architecture.view_builder.collect_raw_package_facts",
    complexity_provider_id="language.java.complexity",
    complexity_maturity=CapabilityMaturity.PARTIAL,
    supported_frameworks=("jpa", "spring-web"),
    framework_structural=True,
    unsupported_syntax=(
        "switch-expression",
        "record-pattern",
        "lambda-bodies-unmeasured",
    ),
    unsupported_frameworks=("jakarta-ee-full", "quarkus", "micronaut"),
    limitations=(
        "Package and declared-package heuristics; Spring/JPA annotation patterns "
        "only. Complexity is brace-aware regex, not javac."
    ),
    notes=("detection_via_suffix_or_java_technology_detector",),
)

JAVASCRIPT_LANGUAGE_PIN = LanguageSupportPin(
    language="javascript",
    launch_tier=DepthTier.DEEPEST_TARGET,
    provider_id="language.javascript.core",
    provider_version="1.0.0",
    detection_suffixes=(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte"),
    structural_maturity=CapabilityMaturity.PARTIAL,
    structural_parser="architecture.view_builder.collect_raw_package_facts",
    complexity_provider_id="language.javascript.complexity",
    complexity_maturity=CapabilityMaturity.PARTIAL,
    supported_frameworks=("angular", "nestjs", "next", "react", "svelte", "vue"),
    framework_structural=True,
    unsupported_syntax=(
        "switch-expression",
        "optional-chaining-as-complexity",
        "nullish-coalescing-as-complexity",
        "typescript-compiler-api",
        "template-expressions",
        "regex-literals",
    ),
    unsupported_frameworks=(),
    limitations=(
        "ES/CommonJS imports and TypeScript import-type only. Directory-path "
        "units; no package.json workspace graph. Framework usage is domain-layer "
        "decorator and quoted import patterns only, no module graph and no "
        "component tree. Complexity is a brace-aware scan of functions, "
        "methods, and assigned arrows, not the TypeScript compiler."
    ),
    notes=(
        "typescript_files_use_javascript_provider",
        "complexity_structural_scan",
        "framework_structural_scan",
    ),
)

PYTHON_LANGUAGE_PIN = LanguageSupportPin(
    language="python",
    launch_tier=DepthTier.VERIFIED_RETAINED,
    provider_id="language.python.core",
    provider_version="1.0.0",
    detection_suffixes=(".py",),
    structural_maturity=CapabilityMaturity.PARTIAL,
    structural_parser="architecture.view_builder.collect_raw_package_facts",
    complexity_provider_id="language.python.complexity",
    complexity_maturity=CapabilityMaturity.PARTIAL,
    supported_frameworks=(),
    framework_structural=False,
    unsupported_syntax=("dynamic-import", "exec-eval", "unsupported-syntax-ast"),
    unsupported_frameworks=("django", "flask", "fastapi"),
    limitations=(
        "Package-path heuristics; TYPE_CHECKING imports are structural. "
        "No framework extractor. Complexity uses the stdlib AST."
    ),
    notes=("detection_via_suffix_or_python_technology_detector",),
)

PHP_LANGUAGE_PIN = LanguageSupportPin(
    language="php",
    launch_tier=DepthTier.VERIFIED_RETAINED,
    provider_id="language.php.core",
    provider_version="1.0.0",
    detection_suffixes=(".php",),
    structural_maturity=CapabilityMaturity.PARTIAL,
    structural_parser="architecture.view_builder.collect_raw_package_facts",
    complexity_provider_id="language.php.complexity",
    complexity_maturity=CapabilityMaturity.PARTIAL,
    supported_frameworks=("codeigniter", "laminas", "laravel", "symfony"),
    framework_structural=True,
    unsupported_syntax=("full-php-ast", "attributes-as-symbols"),
    unsupported_frameworks=("wordpress", "magento", "drupal"),
    limitations=(
        "use / require / include only; namespace or directory path units. "
        "Composer graphs are Dependency Evidence, not this provider."
    ),
    notes=("detection_via_suffix_or_php_technology_detector",),
)

CSHARP_LANGUAGE_PIN = LanguageSupportPin(
    language="csharp",
    launch_tier=DepthTier.VERIFIED_RETAINED,
    provider_id="language.csharp.core",
    provider_version="1.0.0",
    detection_suffixes=(".cs",),
    structural_maturity=CapabilityMaturity.PARTIAL,
    structural_parser="architecture.view_builder.collect_raw_package_facts",
    complexity_provider_id="language.csharp.complexity",
    complexity_maturity=CapabilityMaturity.PARTIAL,
    supported_frameworks=("aspnet-mvc", "aspnetcore", "blazor", "efcore", "wcf"),
    framework_structural=True,
    unsupported_syntax=("roslyn-ast", "source-generators", "file-scoped-namespaces-full"),
    unsupported_frameworks=("maui", "xamarin", "unity"),
    limitations=(
        "using / using static only; no Roslyn AST. NuGet graphs are "
        "Dependency Evidence, not this provider."
    ),
    notes=("detection_via_suffix_or_csharp_technology_detector",),
)

LANGUAGE_SUPPORT_PINS: tuple[LanguageSupportPin, ...] = (
    CSHARP_LANGUAGE_PIN,
    JAVA_LANGUAGE_PIN,
    JAVASCRIPT_LANGUAGE_PIN,
    PHP_LANGUAGE_PIN,
    PYTHON_LANGUAGE_PIN,
)

STRUCTURAL_LANGUAGE_IDS: frozenset[str] = frozenset(pin.language for pin in LANGUAGE_SUPPORT_PINS)

# TypeScript is detected separately but structurally served by the JS provider.
STRUCTURAL_LANGUAGE_LABELS: dict[str, str] = {
    "C#": "csharp",
    "Java": "java",
    "JavaScript": "javascript",
    "PHP": "php",
    "Python": "python",
    "TypeScript": "javascript",
}


def pin_for_language(language: str) -> LanguageSupportPin | None:
    key = language.strip().lower()
    if key == "typescript":
        return JAVASCRIPT_LANGUAGE_PIN
    for pin in LANGUAGE_SUPPORT_PINS:
        if pin.language == key:
            return pin
    return None


def pin_by_provider_id() -> dict[str, LanguageSupportPin]:
    return {pin.provider_id: pin for pin in LANGUAGE_SUPPORT_PINS}
