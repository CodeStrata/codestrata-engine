from codestrata.models import BuildFacts


def test_merge_combines_build_discovery_and_metadata() -> None:
    discovery = BuildFacts(
        build_systems=["maven"],
        build_files=["pom.xml"],
        wrapper_files=["mvnw"],
    )

    metadata = BuildFacts(
        multi_module=True,
        modules=["service-a", "service-b"],
        packaging_types=["pom"],
        java_source_versions=["17"],
        java_target_versions=["17"],
        inferred_commands=[
            "./mvnw test",
            "./mvnw package",
        ],
    )

    result = discovery.merge(metadata)

    assert result.build_systems == ["maven"]
    assert result.build_files == ["pom.xml"]
    assert result.wrapper_files == ["mvnw"]
    assert result.multi_module is True
    assert result.modules == ["service-a", "service-b"]
    assert result.packaging_types == ["pom"]
    assert result.java_source_versions == ["17"]
    assert result.java_target_versions == ["17"]
    assert result.inferred_commands == [
        "./mvnw test",
        "./mvnw package",
    ]


def test_merge_removes_duplicate_values() -> None:
    first = BuildFacts(
        plugins=["maven-compiler-plugin"],
        inferred_commands=["mvn test"],
    )

    second = BuildFacts(
        plugins=["maven-compiler-plugin"],
        inferred_commands=["mvn test", "mvn package"],
    )

    result = first.merge(second)

    assert result.plugins == ["maven-compiler-plugin"]
    assert result.inferred_commands == [
        "mvn test",
        "mvn package",
    ]


def test_merge_sets_multiple_build_systems() -> None:
    first = BuildFacts(build_systems=["maven"])
    second = BuildFacts(build_systems=["npm"])

    result = first.merge(second)

    assert result.build_systems == ["maven", "npm"]
    assert result.multiple_build_systems is True
