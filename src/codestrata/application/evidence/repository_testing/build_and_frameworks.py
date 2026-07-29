"""Build-manifest and declared framework evidence collectors."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from codestrata.application.evidence.repository_testing.discovery import (
    classify_build_manifest,
    normalize_relative_path,
)
from codestrata.application.evidence.repository_testing.redact import redact_command_projection
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    FrameworkEvidenceBasis,
    TestBuildSourceType,
    TestFrameworkFamily,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_config_evidence_id,
    make_framework_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import (
    BuildConfigurationFactEvidence,
    FrameworkFactEvidence,
)

_MAVEN_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("junit-jupiter", TestFrameworkFamily.JUNIT_JUPITER),
    ("junit", TestFrameworkFamily.JUNIT),
    ("testng", TestFrameworkFamily.TESTNG),
    ("mockito", TestFrameworkFamily.MOCKITO),
    ("jacoco", TestFrameworkFamily.JACOCO),
    ("surefire", TestFrameworkFamily.SUREFIRE),
    ("failsafe", TestFrameworkFamily.FAILSAFE),
)

_GRADLE_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("junit", TestFrameworkFamily.JUNIT),
    ("usejunitplatform", TestFrameworkFamily.JUNIT_JUPITER),
    ("testng", TestFrameworkFamily.TESTNG),
    ("mockito", TestFrameworkFamily.MOCKITO),
    ("jacoco", TestFrameworkFamily.JACOCO),
)

_NPM_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("jest", TestFrameworkFamily.JEST),
    ("vitest", TestFrameworkFamily.VITEST),
    ("mocha", TestFrameworkFamily.MOCHA),
    ("playwright", TestFrameworkFamily.PLAYWRIGHT),
    ("cypress", TestFrameworkFamily.CYPRESS),
)

_PYTHON_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("pytest", TestFrameworkFamily.PYTEST),
    ("coverage", TestFrameworkFamily.COVERAGE_PY),
    ("tox", TestFrameworkFamily.TOX),
)

_COMPOSER_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("phpunit/phpunit", TestFrameworkFamily.PHPUNIT),
    ("phpunit", TestFrameworkFamily.PHPUNIT),
    ("pestphp/pest", TestFrameworkFamily.PEST),
)

_DOTNET_FRAMEWORKS: tuple[tuple[str, TestFrameworkFamily], ...] = (
    ("xunit", TestFrameworkFamily.XUNIT),
    ("nunit", TestFrameworkFamily.NUNIT),
    ("mstest", TestFrameworkFamily.MSTEST),
    ("coverlet", TestFrameworkFamily.COVERLET),
)

_XML_VERSION = re.compile(
    r"<version>\s*([^<]+?)\s*</version>",
    re.IGNORECASE,
)


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_build_collector",
        extraction_method="manifest_token_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _framework_fact(
    *,
    framework: TestFrameworkFamily,
    path: str,
    basis: FrameworkEvidenceBasis,
    detail: str | None,
    declared_version: str | None,
    configuration_fingerprint: str,
) -> FrameworkFactEvidence:
    return FrameworkFactEvidence(
        evidence_id=make_framework_evidence_id(
            framework=framework.value,
            path=path,
            basis=basis.value,
        ),
        framework=framework,
        basis=basis,
        path=path,
        declared_version=declared_version,
        detail=detail,
        provenance=_provenance(path, configuration_fingerprint=configuration_fingerprint),
    )


def _build_fact(
    *,
    path: str,
    source_type: TestBuildSourceType,
    fact_kind: str,
    detail: str | None,
    command_projection: str | None,
    framework: TestFrameworkFamily | None,
    configuration_fingerprint: str,
) -> BuildConfigurationFactEvidence:
    return BuildConfigurationFactEvidence(
        evidence_id=make_config_evidence_id(
            path=path,
            kind=fact_kind,
            detail=(detail or command_projection or framework.value if framework else "")[:80],
        ),
        path=path,
        source_type=source_type,
        fact_kind=fact_kind,
        detail=detail,
        command_projection=(
            redact_command_projection(command_projection)
            if command_projection
            else None
        ),
        framework=framework,
        provenance=_provenance(path, configuration_fingerprint=configuration_fingerprint),
    )


def _nearby_xml_version(text: str, token_index: int) -> str | None:
    window = text[max(0, token_index - 120) : token_index + 200]
    match = _XML_VERSION.search(window)
    if match is None:
        return None
    version = match.group(1).strip()
    return version[:40] or None


def _collect_pom(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    lower = text.lower()
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []
    for token, family in _MAVEN_FRAMEWORKS:
        idx = lower.find(token)
        if idx < 0:
            continue
        version = _nearby_xml_version(text, idx)
        frameworks.append(
            _framework_fact(
                framework=family,
                path=path,
                basis=FrameworkEvidenceBasis.DECLARED,
                detail=f"maven:{token}",
                declared_version=version,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
        kind = "plugin" if token in {"surefire", "failsafe", "jacoco"} else "dependency"
        builds.append(
            _build_fact(
                path=path,
                source_type=TestBuildSourceType.MAVEN,
                fact_kind=kind,
                detail=token,
                command_projection=None,
                framework=family,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    return frameworks, builds


def _collect_gradle(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    lower = text.lower()
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []

    if "testimplementation" in lower.replace(" ", ""):
        builds.append(
            _build_fact(
                path=path,
                source_type=TestBuildSourceType.GRADLE,
                fact_kind="test_dependency_configuration",
                detail="testImplementation",
                command_projection=None,
                framework=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    if "usejunitplatform" in lower.replace(" ", ""):
        frameworks.append(
            _framework_fact(
                framework=TestFrameworkFamily.JUNIT_JUPITER,
                path=path,
                basis=FrameworkEvidenceBasis.CONFIGURED,
                detail="useJUnitPlatform",
                declared_version=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
        builds.append(
            _build_fact(
                path=path,
                source_type=TestBuildSourceType.GRADLE,
                fact_kind="test_task_configuration",
                detail="useJUnitPlatform",
                command_projection=None,
                framework=TestFrameworkFamily.JUNIT_JUPITER,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    if "jacoco" in lower:
        frameworks.append(
            _framework_fact(
                framework=TestFrameworkFamily.JACOCO,
                path=path,
                basis=FrameworkEvidenceBasis.DECLARED,
                detail="jacoco",
                declared_version=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    if "integrationtest" in lower.replace(" ", ""):
        builds.append(
            _build_fact(
                path=path,
                source_type=TestBuildSourceType.GRADLE,
                fact_kind="integration_test_task",
                detail="integrationTest",
                command_projection=None,
                framework=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    for token, family in _GRADLE_FRAMEWORKS:
        if token == "usejunitplatform":
            continue
        if token in lower:
            frameworks.append(
                _framework_fact(
                    framework=family,
                    path=path,
                    basis=FrameworkEvidenceBasis.DECLARED,
                    detail=f"gradle:{token}",
                    declared_version=None,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
    return frameworks, builds


def _collect_package_json(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        lower = text.lower()
        for token, family in _NPM_FRAMEWORKS:
            if token in lower:
                frameworks.append(
                    _framework_fact(
                        framework=family,
                        path=path,
                        basis=FrameworkEvidenceBasis.DECLARED,
                        detail=f"package.json:{token}",
                        declared_version=None,
                        configuration_fingerprint=configuration_fingerprint,
                    )
                )
        return frameworks, builds

    if not isinstance(data, dict):
        return frameworks, builds

    deps: dict[str, object] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update(section)

    for token, family in _NPM_FRAMEWORKS:
        matched = next(
            (
                (name, ver)
                for name, ver in deps.items()
                if token == str(name).lower() or token in str(name).lower()
            ),
            None,
        )
        if matched is None:
            continue
        name, ver = matched
        version = str(ver).lstrip("^~>=< ")[:40] if ver is not None else None
        frameworks.append(
            _framework_fact(
                framework=family,
                path=path,
                basis=FrameworkEvidenceBasis.DECLARED,
                detail=f"package.json:{name}",
                declared_version=version or None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )

    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for script_name, command in sorted(
            scripts.items(), key=lambda item: str(item[0])
        ):
            name = str(script_name)
            if name != "test" and not name.startswith("test:"):
                continue
            command_text = str(command)
            tool_family = None
            lower_cmd = command_text.lower()
            for token, family in _NPM_FRAMEWORKS:
                if token in lower_cmd:
                    tool_family = family
                    break
            builds.append(
                _build_fact(
                    path=path,
                    source_type=TestBuildSourceType.NPM,
                    fact_kind="test_script",
                    detail=name,
                    command_projection=command_text,
                    framework=tool_family,
                    configuration_fingerprint=configuration_fingerprint,
                )
            )
            if tool_family is not None:
                frameworks.append(
                    _framework_fact(
                        framework=tool_family,
                        path=path,
                        basis=FrameworkEvidenceBasis.INVOKED,
                        detail=f"script:{name}",
                        declared_version=None,
                        configuration_fingerprint=configuration_fingerprint,
                    )
                )
    return frameworks, builds


def _collect_python_manifest(
    path: str,
    text: str,
    source_type: TestBuildSourceType,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    lower = text.lower()
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []
    for token, family in _PYTHON_FRAMEWORKS:
        if token not in lower:
            continue
        frameworks.append(
            _framework_fact(
                framework=family,
                path=path,
                basis=(
                    FrameworkEvidenceBasis.CONFIGURED
                    if source_type is TestBuildSourceType.STANDALONE_CONFIG
                    else FrameworkEvidenceBasis.DECLARED
                ),
                detail=f"{source_type.value}:{token}",
                declared_version=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
        builds.append(
            _build_fact(
                path=path,
                source_type=source_type,
                fact_kind="test_tool_declaration",
                detail=token,
                command_projection=None,
                framework=family,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    return frameworks, builds


def _collect_csproj(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    lower = text.lower()
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []
    for token, family in _DOTNET_FRAMEWORKS:
        if token not in lower:
            continue
        frameworks.append(
            _framework_fact(
                framework=family,
                path=path,
                basis=FrameworkEvidenceBasis.DECLARED,
                detail=f"csproj:{token}",
                declared_version=None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
        builds.append(
            _build_fact(
                path=path,
                source_type=TestBuildSourceType.DOTNET_PROJECT,
                fact_kind="package_reference",
                detail=token,
                command_projection=None,
                framework=family,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    return frameworks, builds



def _collect_composer_json(
    path: str,
    text: str,
    *,
    configuration_fingerprint: str,
) -> tuple[list[FrameworkFactEvidence], list[BuildConfigurationFactEvidence]]:
    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        lower = text.lower()
        for token, family in _COMPOSER_FRAMEWORKS:
            if token in lower:
                frameworks.append(
                    _framework_fact(
                        framework=family,
                        path=path,
                        basis=FrameworkEvidenceBasis.DECLARED,
                        detail=f"composer.json:{token}",
                        declared_version=None,
                        configuration_fingerprint=configuration_fingerprint,
                    )
                )
        return frameworks, builds

    if not isinstance(data, dict):
        return frameworks, builds

    deps: dict[str, object] = {}
    for key in ("require", "require-dev"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update(section)

    for token, family in _COMPOSER_FRAMEWORKS:
        matched = next(
            (
                (name, ver)
                for name, ver in deps.items()
                if token == str(name).lower() or token in str(name).lower()
            ),
            None,
        )
        if matched is None:
            continue
        name, ver = matched
        version = str(ver).lstrip("^~>=< ")[:40] if ver is not None else None
        frameworks.append(
            _framework_fact(
                framework=family,
                path=path,
                basis=FrameworkEvidenceBasis.DECLARED,
                detail=f"composer.json:{name}",
                declared_version=version or None,
                configuration_fingerprint=configuration_fingerprint,
            )
        )
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for script_name, command in sorted(scripts.items()):
            cmd = command if isinstance(command, str) else " ".join(
                str(item) for item in command
            ) if isinstance(command, list) else None
            if cmd is None:
                continue
            lower = cmd.lower()
            if "phpunit" in lower or "pest" in lower or str(script_name).lower() == "test":
                builds.append(
                    _build_fact(
                        path=path,
                        source_type=TestBuildSourceType.COMPOSER,
                        fact_kind="composer_script",
                        detail=str(script_name),
                        command_projection=redact_command_projection(cmd)[:200],
                        framework=(
                            TestFrameworkFamily.PHPUNIT
                            if "phpunit" in lower
                            else TestFrameworkFamily.PEST if "pest" in lower else None
                        ),
                        configuration_fingerprint=configuration_fingerprint,
                    )
                )
    return frameworks, builds



def collect_build_and_framework_facts(
    file_texts: Mapping[str, str],
    *,
    configuration_fingerprint: str = "",
) -> tuple[tuple[FrameworkFactEvidence, ...], tuple[BuildConfigurationFactEvidence, ...]]:
    """Collect framework and build-configuration facts from manifest texts."""

    frameworks: list[FrameworkFactEvidence] = []
    builds: list[BuildConfigurationFactEvidence] = []

    for raw_path, text in sorted(file_texts.items(), key=lambda item: item[0]):
        path = normalize_relative_path(raw_path)
        source = classify_build_manifest(path)
        if source is None:
            continue
        if source is TestBuildSourceType.MAVEN:
            fw, bd = _collect_pom(
                path, text, configuration_fingerprint=configuration_fingerprint
            )
        elif source is TestBuildSourceType.GRADLE:
            fw, bd = _collect_gradle(
                path, text, configuration_fingerprint=configuration_fingerprint
            )
        elif source is TestBuildSourceType.NPM:
            fw, bd = _collect_package_json(
                path, text, configuration_fingerprint=configuration_fingerprint
            )
        elif path.lower().endswith(("phpunit.xml", "phpunit.xml.dist")):
            fw = [
                _framework_fact(
                    framework=TestFrameworkFamily.PHPUNIT,
                    path=path,
                    basis=FrameworkEvidenceBasis.CONFIGURED,
                    detail="phpunit.xml",
                    declared_version=None,
                    configuration_fingerprint=configuration_fingerprint,
                )
            ]
            bd = []
        elif source in {
            TestBuildSourceType.PYTHON_PROJECT,
            TestBuildSourceType.REQUIREMENTS,
            TestBuildSourceType.TOX,
            TestBuildSourceType.STANDALONE_CONFIG,
        }:
            fw, bd = _collect_python_manifest(
                path,
                text,
                source,
                configuration_fingerprint=configuration_fingerprint,
            )
        elif source is TestBuildSourceType.DOTNET_PROJECT:
            fw, bd = _collect_csproj(
                path, text, configuration_fingerprint=configuration_fingerprint
            )
        elif source is TestBuildSourceType.COMPOSER:
            fw, bd = _collect_composer_json(
                path, text, configuration_fingerprint=configuration_fingerprint
            )
        else:
            continue
        frameworks.extend(fw)
        builds.extend(bd)

    # Deterministic de-dupe by evidence_id.
    framework_by_id = {item.evidence_id: item for item in frameworks}
    build_by_id = {item.evidence_id: item for item in builds}
    return (
        tuple(sorted(framework_by_id.values(), key=lambda item: item.evidence_id)),
        tuple(sorted(build_by_id.values(), key=lambda item: item.evidence_id)),
    )
