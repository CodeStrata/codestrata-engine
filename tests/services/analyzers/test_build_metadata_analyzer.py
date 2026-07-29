from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers import BuildMetadataAnalyzer


def test_extracts_maven_metadata(tmp_path: Path) -> None:
    pom = tmp_path / "pom.xml"
    pom.write_text(
        """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
            <modelVersion>4.0.0</modelVersion>

            <groupId>com.example</groupId>
            <artifactId>example-parent</artifactId>
            <version>1.0.0</version>
            <packaging>pom</packaging>

            <properties>
                <java.version>17</java.version>
                <maven.compiler.source>17</maven.compiler.source>
                <maven.compiler.target>17</maven.compiler.target>
            </properties>

            <modules>
                <module>service-api</module>
                <module>service-core</module>
            </modules>

            <build>
                <plugins>
                    <plugin>
                        <groupId>org.apache.maven.plugins</groupId>
                        <artifactId>maven-compiler-plugin</artifactId>
                    </plugin>
                </plugins>
            </build>
        </project>
        """,
        encoding="utf-8",
    )

    (tmp_path / "mvnw").write_text("", encoding="utf-8")

    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[
            "pom.xml",
            "mvnw",
        ],
    )

    result = BuildMetadataAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    assert result.facts.build is not None

    facts = result.facts.build

    assert facts.multi_module
    assert facts.modules == ["service-api", "service-core"]
    assert facts.packaging_types == ["pom"]
    assert facts.plugins == ["org.apache.maven.plugins:maven-compiler-plugin"]
    assert facts.java_source_versions == ["17"]
    assert facts.java_target_versions == ["17"]


def test_handles_invalid_maven_xml(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        "<project>",
        encoding="utf-8",
    )

    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["pom.xml"],
    )

    result = BuildMetadataAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    assert result.facts.build is not None
    assert result.facts.build.modules == []
    assert result.findings == []
