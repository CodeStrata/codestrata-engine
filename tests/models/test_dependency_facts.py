from codestrata.models import (
    Dependency,
    DependencyFacts,
    DependencyManifest,
)


def test_merge_combines_dependency_discovery_and_metadata() -> None:
    discovery = DependencyFacts(
        manifests=[
            DependencyManifest(
                path="package.json",
                ecosystem="npm",
                manifest_type="manifest",
            )
        ]
    )

    metadata = DependencyFacts(
        dependencies=[
            Dependency(
                name="react",
                version="^19.0.0",
                ecosystem="npm",
                scope="runtime",
                manifest_path="package.json",
                categories=["framework"],
                dynamic_version=True,
            )
        ],
        framework_dependencies=["react"],
        dynamic_version_dependencies=["react"],
    )

    result = discovery.merge(metadata)

    assert len(result.manifests) == 1
    assert len(result.dependencies) == 1
    assert result.direct_dependency_count == 1
    assert result.framework_dependencies == ["react"]
    assert result.dynamic_version_dependencies == ["react"]


def test_merge_removes_duplicate_manifests() -> None:
    manifest = DependencyManifest(
        path="pom.xml",
        ecosystem="maven",
        manifest_type="manifest",
    )

    result = DependencyFacts(manifests=[manifest]).merge(DependencyFacts(manifests=[manifest]))

    assert result.manifests == [manifest]
