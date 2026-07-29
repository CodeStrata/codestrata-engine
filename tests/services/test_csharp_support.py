"""Phase 5.18 C# / .NET support unit tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.dependency.nuget_collector import (
    collect_nuget_dependency_bundle,
)
from codestrata.application.evidence.language.providers.csharp_provider import (
    CsharpLanguageEvidenceProvider,
)
from codestrata.application.rules.architecture.view_builder import (
    collect_raw_package_facts,
    extract_imports,
)
from codestrata.domain.evidence.dependency.enums import DependencyEcosystem
from codestrata.domain.evidence.language.contracts import LanguageEvidenceContext
from codestrata.models import Repository
from codestrata.services.analyzers.dependency_metadata_analyzer import (
    DependencyMetadataAnalyzer,
)
from codestrata.services.detectors.csharp_technology_detector import CsharpTechnologyDetector
from codestrata.services.repository_graph.extractors.nuget_parser import (
    parse_nuget_dependencies,
)


def test_csharp_detector_frameworks(tmp_path: Path) -> None:
    (tmp_path / "App.csproj").write_text(
        """
        <Project Sdk="Microsoft.NET.Sdk.Web">
          <PropertyGroup>
            <TargetFramework>net8.0</TargetFramework>
          </PropertyGroup>
          <ItemGroup>
            <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
            <PackageReference Include="xunit" Version="2.9.0" />
            <PackageReference Include="Microsoft.AspNetCore.Components" Version="8.0.0" />
          </ItemGroup>
        </Project>
        """,
        encoding="utf-8",
    )
    (tmp_path / "Legacy.csproj").write_text(
        """
        <Project ToolsVersion="15.0">
          <PropertyGroup>
            <TargetFrameworkVersion>v4.8</TargetFrameworkVersion>
          </PropertyGroup>
        </Project>
        """,
        encoding="utf-8",
    )
    (tmp_path / "packages.config").write_text(
        """
        <packages>
          <package id="EntityFramework" version="6.4.4" />
          <package id="System.ServiceModel.Http" version="4.10.0" />
        </packages>
        """,
        encoding="utf-8",
    )
    (tmp_path / "Program.cs").write_text(
        "using Microsoft.AspNetCore.Mvc;\nusing System.ServiceModel;\n",
        encoding="utf-8",
    )
    (tmp_path / "global.json").write_text('{"sdk":{"version":"8.0.100"}}', encoding="utf-8")
    repository = Repository(
        name="csharp-sample",
        path=tmp_path,
        files=[
            "App.csproj",
            "Legacy.csproj",
            "packages.config",
            "Program.cs",
            "global.json",
            "App.sln",
        ],
    )
    (tmp_path / "App.sln").write_text("Microsoft Visual Studio Solution File\n", encoding="utf-8")
    technologies = CsharpTechnologyDetector().detect(repository)
    names = {item.name for item in technologies}
    assert "C#" in names
    assert "NuGet" in names
    assert ".NET" in names or ".NET Framework" in names
    assert "ASP.NET Core" in names
    assert "Entity Framework Core" in names
    assert "Blazor" in names
    assert "xUnit" in names
    assert "WCF" in names or "Entity Framework" in names


def test_nuget_metadata_and_graph_parser(tmp_path: Path) -> None:
    manifest = tmp_path / "App.csproj"
    payload = """
    <Project Sdk="Microsoft.NET.Sdk">
      <ItemGroup>
        <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
        <PackageReference Include="xunit" Version="2.9.0" />
      </ItemGroup>
    </Project>
    """
    manifest.write_text(payload, encoding="utf-8")
    repository = Repository(
        name="nuget-deps",
        path=tmp_path,
        files=["App.csproj"],
    )
    result = DependencyMetadataAnalyzer().analyze(repository, technologies=[])
    deps = result.facts.dependencies.dependencies if result.facts.dependencies else []
    names = {item.name for item in deps}
    assert "Newtonsoft.Json" in names
    assert "xunit" in names
    assert all(item.ecosystem == "nuget" for item in deps)

    parsed = parse_nuget_dependencies(payload.encode("utf-8"), source_file="App.csproj")
    assert any(item.name == "Newtonsoft.Json" for item in parsed)


def test_csharp_import_extraction_and_units() -> None:
    text = """
namespace SampleAspNet.Controllers;
using SampleAspNet.Models;
using SampleAspNet.Services;
"""
    imports = extract_imports("src/Controllers/UsersController.cs", text)
    assert "SampleAspNet.Models" in imports
    assert "SampleAspNet.Services" in imports
    facts = collect_raw_package_facts(
        relative_paths=["src/Controllers/UsersController.cs"],
        file_texts={"src/Controllers/UsersController.cs": text},
        language_filter="csharp",
    )
    assert facts.files_parsed == 1
    assert any("controller" in unit or "sampleaspnet" in unit for unit in facts.package_files)


def test_csharp_language_provider_and_nuget_evidence(tmp_path: Path) -> None:
    csproj = """
    <Project Sdk="Microsoft.NET.Sdk.Web">
      <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
      <ItemGroup>
        <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
      </ItemGroup>
    </Project>
    """
    source = """
namespace Sample.Api;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
[ApiController]
public class ItemsController {}
"""
    paths = ["App.csproj", "ItemsController.cs"]
    texts = {"App.csproj": csproj, "ItemsController.cs": source}
    provider = CsharpLanguageEvidenceProvider()
    context = LanguageEvidenceContext(
        repository_id="repo",
        relative_paths=tuple(paths),
        file_texts=texts,
        configuration={},
    )
    result = provider.collect(context)
    assert result.status.value in {"succeeded", "partially_succeeded"}
    assert result.bundle is not None

    bundle = collect_nuget_dependency_bundle(
        relative_paths=paths,
        file_texts=texts,
        ignore_path_markers=(),
    )
    assert bundle.ecosystem is DependencyEcosystem.NUGET
    assert any(
        item.normalized_identity == "microsoft.entityframeworkcore"
        for item in bundle.declarations
    )
