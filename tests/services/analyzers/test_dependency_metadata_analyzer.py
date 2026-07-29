import json
from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers import DependencyMetadataAnalyzer


def test_extracts_maven_dependencies(tmp_path: Path) -> None:
    pom = tmp_path / "pom.xml"

    pom.write_text(
        """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
            <modelVersion>4.0.0</modelVersion>

            <properties>
                <spring.version>3.5.0</spring.version>
            </properties>

            <dependencies>
                <dependency>
                    <groupId>org.springframework.boot</groupId>
                    <artifactId>spring-boot-starter-web</artifactId>
                    <version>${spring.version}</version>
                </dependency>

                <dependency>
                    <groupId>org.junit.jupiter</groupId>
                    <artifactId>junit-jupiter</artifactId>
                    <version>5.12.0</version>
                    <scope>test</scope>
                </dependency>

                <dependency>
                    <groupId>org.postgresql</groupId>
                    <artifactId>postgresql</artifactId>
                </dependency>
            </dependencies>
        </project>
        """,
        encoding="utf-8",
    )

    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["pom.xml"],
    )

    result = DependencyMetadataAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    facts = result.facts.dependencies

    assert facts is not None
    assert facts.direct_dependency_count == 3
    assert facts.test_dependency_count == 1

    dependencies = {dependency.name: dependency for dependency in facts.dependencies}

    spring = dependencies["org.springframework.boot:spring-boot-starter-web"]
    assert spring.version == "3.5.0"
    assert spring.scope == "runtime"
    assert spring.categories == ["framework"]

    junit = dependencies["org.junit.jupiter:junit-jupiter"]
    assert junit.scope == "test"
    assert "testing" in junit.categories

    postgresql = dependencies["org.postgresql:postgresql"]
    assert postgresql.unmanaged_version is True

    assert facts.framework_dependencies == ["org.springframework.boot:spring-boot-starter-web"]
    assert facts.database_drivers == ["org.postgresql:postgresql"]
    assert facts.testing_libraries == ["org.junit.jupiter:junit-jupiter"]


def test_extracts_npm_dependencies(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"

    package_json.write_text(
        json.dumps(
            {
                "dependencies": {
                    "react": "^19.0.0",
                    "@aws-sdk/client-s3": "3.800.0",
                    "jsonwebtoken": "9.0.2",
                },
                "devDependencies": {
                    "jest": "~30.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["package.json"],
    )

    result = DependencyMetadataAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    facts = result.facts.dependencies

    assert facts is not None
    assert facts.direct_dependency_count == 4
    assert facts.development_dependency_count == 1
    assert facts.test_dependency_count == 1

    dependencies = {dependency.name: dependency for dependency in facts.dependencies}

    assert dependencies["react"].dynamic_version is True
    assert dependencies["jest"].scope == "development"
    assert dependencies["jest"].dynamic_version is True

    assert facts.framework_dependencies == ["react"]
    assert facts.cloud_sdks == ["@aws-sdk/client-s3"]
    assert facts.testing_libraries == ["jest"]
    assert facts.security_libraries == ["jsonwebtoken"]

    assert facts.dynamic_version_dependencies == [
        "jest",
        "react",
    ]


def test_handles_invalid_manifest_files(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        "<project>",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[
            "pom.xml",
            "package.json",
        ],
    )

    result = DependencyMetadataAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    assert result.facts.dependencies is not None
    assert result.facts.dependencies.dependencies == []
    assert result.findings == []
