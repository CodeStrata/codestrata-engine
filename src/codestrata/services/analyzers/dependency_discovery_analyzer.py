"""Discover dependency manifests and lockfiles."""

from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    DependencyFacts,
    DependencyManifest,
    Repository,
    RepositoryFacts,
    Technology,
)


class DependencyDiscoveryAnalyzer:
    """Discover dependency manifests without parsing dependencies."""

    MANIFESTS: dict[str, tuple[str, str]] = {
        "pom.xml": ("maven", "manifest"),
        "build.gradle": ("gradle", "manifest"),
        "build.gradle.kts": ("gradle", "manifest"),
        "package.json": ("npm", "manifest"),
        "composer.json": ("composer", "manifest"),
        "packages.config": ("nuget", "manifest"),
        "Directory.Packages.props": ("nuget", "manifest"),
        "requirements.txt": ("python", "manifest"),
        "pyproject.toml": ("python", "manifest"),
        "Pipfile": ("python", "manifest"),
        "go.mod": ("go", "manifest"),
        "Cargo.toml": ("cargo", "manifest"),
    }

    LOCKFILES: dict[str, tuple[str, str]] = {
        "package-lock.json": ("npm", "lockfile"),
        "npm-shrinkwrap.json": ("npm", "lockfile"),
        "yarn.lock": ("yarn", "lockfile"),
        "pnpm-lock.yaml": ("pnpm", "lockfile"),
        "composer.lock": ("composer", "lockfile"),
        "packages.lock.json": ("nuget", "lockfile"),
        "Pipfile.lock": ("python", "lockfile"),
        "poetry.lock": ("python", "lockfile"),
        "uv.lock": ("python", "lockfile"),
        "go.sum": ("go", "lockfile"),
        "Cargo.lock": ("cargo", "lockfile"),
        "gradle.lockfile": ("gradle", "lockfile"),
    }

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Discover dependency-related files."""

        del technologies
        del facts

        manifests: list[DependencyManifest] = []

        for relative_path in repository.files:
            filename = Path(relative_path).name

            manifest_definition = self.MANIFESTS.get(filename)
            if manifest_definition is None and filename.lower() == "directory.packages.props":
                manifest_definition = ("nuget", "manifest")
            if manifest_definition is None and filename.lower().endswith(
                (".csproj", ".fsproj", ".vbproj")
            ):
                manifest_definition = ("nuget", "manifest")
            if manifest_definition is not None:
                ecosystem, manifest_type = manifest_definition
                manifests.append(
                    DependencyManifest(
                        path=relative_path,
                        ecosystem=ecosystem,
                        manifest_type=manifest_type,
                        lockfile=False,
                    )
                )
                continue

            lockfile_definition = self.LOCKFILES.get(filename)
            if lockfile_definition is None and filename.lower() == "packages.lock.json":
                lockfile_definition = ("nuget", "lockfile")
            if lockfile_definition is not None:
                ecosystem, manifest_type = lockfile_definition
                manifests.append(
                    DependencyManifest(
                        path=relative_path,
                        ecosystem=ecosystem,
                        manifest_type=manifest_type,
                        lockfile=True,
                    )
                )

        manifests.sort(key=lambda manifest: manifest.path)

        return AnalyzerResult(
            findings=[],
            facts=RepositoryFacts(
                dependencies=DependencyFacts(
                    manifests=manifests,
                )
            ),
        )
