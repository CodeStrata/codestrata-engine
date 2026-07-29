"""Technology detector for C# / .NET repositories."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from codestrata.models import Repository, Technology, TechnologyCategory

_TARGET_FRAMEWORK = re.compile(
    r"<(?:TargetFramework|TargetFrameworks|TargetFrameworkVersion)>\s*([^<]+)\s*<",
    re.IGNORECASE,
)
_PACKAGE_REFERENCE = re.compile(
    r"""<PackageReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["']"""
    r"""[^>]*(?:\bVersion\s*=\s*["']([^"']+)["'])?""",
    re.IGNORECASE,
)
_PACKAGE_REFERENCE_VERSION_CHILD = re.compile(
    r"""<PackageReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["'][^>]*>"""
    r"""\s*<Version>\s*([^<]+)\s*</Version>""",
    re.IGNORECASE | re.DOTALL,
)
_PROJECT_SDK = re.compile(r"""<Project\b[^>]*\bSdk\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_PACKAGES_CONFIG_PACKAGE = re.compile(
    r"""<package\b[^>]*\bid\s*=\s*["']([^"']+)["']"""
    r"""[^>]*\bversion\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

_FRAMEWORK_PACKAGES: dict[str, str] = {
    "microsoft.aspnetcore.app": "ASP.NET Core",
    "microsoft.aspnetcore.mvc": "ASP.NET Core",
    "microsoft.aspnetcore": "ASP.NET Core",
    "microsoft.aspnet.mvc": "ASP.NET MVC",
    "microsoft.aspnet.webapi": "ASP.NET Web API",
    "microsoft.aspnetcore.components": "Blazor",
    "microsoft.aspnetcore.components.web": "Blazor",
    "microsoft.aspnetcore.components.server": "Blazor",
    "microsoft.entityframeworkcore": "Entity Framework Core",
    "microsoft.entityframeworkcore.sqlserver": "Entity Framework Core",
    "entityframework": "Entity Framework",
    "system.servicemodel.primitives": "WCF",
    "system.servicemodel.http": "WCF",
    "system.servicemodel": "WCF",
}

_TEST_PACKAGES: dict[str, str] = {
    "xunit": "xUnit",
    "xunit.runner.visualstudio": "xUnit",
    "nunit": "NUnit",
    "nunit3testadapter": "NUnit",
    "mstest.testframework": "MSTest",
    "microsoft.net.test.sdk": "MSTest",
}


class CsharpTechnologyDetector:
    """Detects C# / .NET ecosystem technologies."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect C# / .NET ecosystem technologies."""

        file_set = set(repository.files)
        technologies: list[Technology] = []

        cs_files = [path for path in repository.files if path.lower().endswith(".cs")]
        csproj_files = [path for path in repository.files if path.lower().endswith(".csproj")]
        fsproj_files = [path for path in repository.files if path.lower().endswith(".fsproj")]
        sln_files = [path for path in repository.files if path.lower().endswith(".sln")]
        has_dotnet_markers = any(
            Path(path).name.lower()
            in {
                "global.json",
                "directory.build.props",
                "directory.packages.props",
                "packages.config",
                "packages.lock.json",
                "nuget.config",
            }
            for path in repository.files
        )

        if cs_files or csproj_files or fsproj_files or sln_files or has_dotnet_markers:
            technologies.append(
                Technology(
                    name="C#",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0 if cs_files or csproj_files else 0.85,
                    source="file_extension_or_dotnet_manifest",
                )
            )

        if csproj_files or fsproj_files or sln_files or has_dotnet_markers:
            technologies.append(
                Technology(
                    name="NuGet",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="dotnet_project_or_nuget_manifest",
                )
            )
            technologies.append(
                Technology(
                    name=".NET SDK / MSBuild",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=0.95,
                    source="dotnet_project_or_solution",
                )
            )

        package_versions = self._collect_package_versions(repository, csproj_files)
        tfms = self._collect_target_frameworks(repository, csproj_files)

        for label in self._runtime_labels(tfms):
            technologies.append(
                Technology(
                    name=label,
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.95,
                    source="csproj_targetframework",
                )
            )

        for package_name, version in package_versions.items():
            lower = package_name.lower()
            framework_name = self._match_package_map(lower, _FRAMEWORK_PACKAGES)
            if framework_name is not None:
                technologies.append(
                    Technology(
                        name=framework_name,
                        version=version,
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=1.0,
                        source="csproj_or_packages_config",
                    )
                )
            test_name = self._match_package_map(lower, _TEST_PACKAGES)
            if test_name is not None:
                technologies.append(
                    Technology(
                        name=test_name,
                        version=version,
                        category=TechnologyCategory.TESTING,
                        confidence=1.0,
                        source="csproj_or_packages_config",
                    )
                )

        # Structural heuristics from source markers.
        source_blob = self._sample_csharp_text(repository, cs_files)
        if "Microsoft.AspNetCore" in source_blob or "[ApiController]" in source_blob:
            technologies.append(
                Technology(
                    name="ASP.NET Core",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="csharp_source_markers",
                )
            )
        if "System.ServiceModel" in source_blob or ".svc" in " ".join(file_set).lower():
            technologies.append(
                Technology(
                    name="WCF",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="csharp_source_or_svc",
                )
            )
        if (
            "Microsoft.AspNetCore.Components" in source_blob
            or "@page" in source_blob
            or any(path.lower().endswith(".razor") for path in repository.files)
        ):
            technologies.append(
                Technology(
                    name="Blazor",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="csharp_blazor_markers",
                )
            )
        if "Microsoft.EntityFrameworkCore" in source_blob or "DbContext" in source_blob:
            technologies.append(
                Technology(
                    name="Entity Framework Core",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.85,
                    source="csharp_source_markers",
                )
            )
        if "System.Web.Mvc" in source_blob or "System.Web.Http" in source_blob:
            technologies.append(
                Technology(
                    name="ASP.NET MVC",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.85,
                    source="csharp_source_markers",
                )
            )

        sdk_blob = " ".join(
            self._read_text(repository, path) for path in csproj_files[:20]
        )
        if "Microsoft.NET.Sdk.Web" in sdk_blob:
            technologies.append(
                Technology(
                    name="ASP.NET Core",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.95,
                    source="csproj_sdk",
                )
            )

        return self._dedupe_technologies(technologies)

    @staticmethod
    def _match_package_map(package_name: str, mapping: dict[str, str]) -> str | None:
        """Match longest package prefix first to avoid AspNetCore swallowing Blazor."""

        candidates = [
            (prefix, label)
            for prefix, label in mapping.items()
            if package_name == prefix or package_name.startswith(prefix + ".")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: len(item[0]), reverse=True)
        return candidates[0][1]

    def _collect_package_versions(
        self,
        repository: Repository,
        csproj_files: list[str],
    ) -> dict[str, str]:
        packages: dict[str, str] = {}
        for relative in csproj_files:
            text = self._read_text(repository, relative)
            for match in _PACKAGE_REFERENCE.finditer(text):
                name = match.group(1).strip()
                version = (match.group(2) or "").strip()
                if name:
                    packages.setdefault(name, version)
            for match in _PACKAGE_REFERENCE_VERSION_CHILD.finditer(text):
                name = match.group(1).strip()
                version = match.group(2).strip()
                if name:
                    packages[name] = version
        for relative in repository.files:
            if Path(relative).name.lower() != "packages.config":
                continue
            text = self._read_text(repository, relative)
            for match in _PACKAGES_CONFIG_PACKAGE.finditer(text):
                packages[match.group(1).strip()] = match.group(2).strip()
        return packages

    def _collect_target_frameworks(
        self,
        repository: Repository,
        csproj_files: list[str],
    ) -> list[str]:
        values: list[str] = []
        for relative in csproj_files:
            text = self._read_text(repository, relative)
            for match in _TARGET_FRAMEWORK.finditer(text):
                raw = match.group(1).strip()
                for part in re.split(r"[;,\s]+", raw):
                    if part.strip():
                        values.append(part.strip())
        return values

    def _runtime_labels(self, tfms: list[str]) -> list[str]:
        labels: list[str] = []
        for tfm in tfms:
            lower = tfm.lower().lstrip("v")
            if lower.startswith("netframework") or re.match(r"^4\.\d", lower):
                labels.append(".NET Framework")
            elif lower.startswith("netcoreapp"):
                labels.append(".NET Core")
            elif lower.startswith("netstandard"):
                labels.append(".NET Standard")
            elif re.match(r"^net\d", lower):
                labels.append(".NET")
            elif lower.startswith("net"):
                # net48 style Framework monikers
                if re.match(r"^net[0-4]\d", lower):
                    labels.append(".NET Framework")
                else:
                    labels.append(".NET")
        return labels

    def _sample_csharp_text(self, repository: Repository, cs_files: list[str]) -> str:
        chunks: list[str] = []
        for relative in cs_files[:40]:
            chunks.append(self._read_text(repository, relative)[:4000])
        return "\n".join(chunks)

    def _read_text(self, repository: Repository, relative: str) -> str:
        path = repository.path / relative
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _dedupe_technologies(self, technologies: list[Technology]) -> list[Technology]:
        ranked: dict[str, Technology] = {}
        for technology in technologies:
            existing = ranked.get(technology.name)
            left = technology.confidence if technology.confidence is not None else 0.0
            if existing is not None and existing.confidence is not None:
                right = existing.confidence
            else:
                right = -1.0
            if existing is None or left > right:
                ranked[technology.name] = technology
            elif (
                existing is not None
                and left == right
                and technology.version
                and not existing.version
            ):
                ranked[technology.name] = technology
        return list(ranked.values())


def parse_csproj_xml_root(text: str) -> ET.Element | None:
    """Best-effort parse helper for callers that prefer ElementTree."""

    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def extract_project_metadata(text: str) -> dict[str, Any]:
    """Extract lightweight project metadata from a .csproj document."""

    frameworks: list[str] = []
    for match in _TARGET_FRAMEWORK.finditer(text):
        for part in re.split(r"[;,\s]+", match.group(1)):
            if part.strip():
                frameworks.append(part.strip())
    sdk_match = _PROJECT_SDK.search(text)
    packages: list[tuple[str, str]] = []
    for match in _PACKAGE_REFERENCE.finditer(text):
        packages.append((match.group(1).strip(), (match.group(2) or "").strip()))
    project_refs = re.findall(
        r"""<ProjectReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["']""",
        text,
        flags=re.IGNORECASE,
    )
    return {
        "sdk": sdk_match.group(1).strip() if sdk_match else None,
        "target_frameworks": frameworks,
        "package_references": packages,
        "project_references": project_refs,
    }
