"""Tests for technology detectors."""

import json
from pathlib import Path

from codestrata.models import Repository
from codestrata.services.detectors import (
    CompositeTechnologyDetector,
    JavaScriptTechnologyDetector,
    JavaTechnologyDetector,
    PhpTechnologyDetector,
    PythonTechnologyDetector,
)


def create_repository(tmp_path: Path) -> Repository:
    """Create a repository model from files under tmp_path."""

    files = sorted(
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()
    )

    return Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=files,
        total_files=len(files),
    )


def test_java_detector_detects_java_maven_and_spring_boot(
    tmp_path: Path,
) -> None:
    """Java detector should identify Java, Maven, and Spring Boot."""

    java_directory = tmp_path / "src" / "main" / "java"
    java_directory.mkdir(parents=True)

    (java_directory / "Application.java").write_text(
        "public class Application {}",
        encoding="utf-8",
    )

    (tmp_path / "pom.xml").write_text(
        """
        <project>
            <dependency>
                <artifactId>spring-boot-starter-web</artifactId>
            </dependency>
            <dependency>
                <artifactId>junit-jupiter</artifactId>
            </dependency>
        </project>
        """,
        encoding="utf-8",
    )

    repository = create_repository(tmp_path)

    technologies = JavaTechnologyDetector().detect(repository)

    technology_names = {technology.name for technology in technologies}

    assert "Java" in technology_names
    assert "Maven" in technology_names
    assert "Spring Boot" in technology_names
    assert "JUnit" in technology_names


def test_javascript_detector_detects_react_and_jest(
    tmp_path: Path,
) -> None:
    """JavaScript detector should identify React and Jest."""

    package_data = {
        "dependencies": {
            "react": "^19.0.0",
        },
        "devDependencies": {
            "jest": "^30.0.0",
        },
    }

    (tmp_path / "package.json").write_text(
        json.dumps(package_data),
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        "console.log('app');",
        encoding="utf-8",
    )

    repository = create_repository(tmp_path)

    technologies = JavaScriptTechnologyDetector().detect(repository)

    technology_names = {technology.name for technology in technologies}

    assert "JavaScript" in technology_names
    assert "Node.js" in technology_names
    assert "npm" in technology_names
    assert "React" in technology_names
    assert "Jest" in technology_names


def test_php_detector_detects_laravel_and_phpunit(
    tmp_path: Path,
) -> None:
    """PHP detector should identify Composer, Laravel, and PHPUnit."""

    composer_data = {
        "require": {
            "php": "^8.3",
            "laravel/framework": "^12.0",
        },
        "require-dev": {
            "phpunit/phpunit": "^12.0",
        },
    }

    (tmp_path / "composer.json").write_text(
        json.dumps(composer_data),
        encoding="utf-8",
    )
    (tmp_path / "artisan").write_text(
        "#!/usr/bin/env php",
        encoding="utf-8",
    )
    (tmp_path / "index.php").write_text(
        "<?php echo 'hello';",
        encoding="utf-8",
    )

    repository = create_repository(tmp_path)

    technologies = PhpTechnologyDetector().detect(repository)

    technology_names = {technology.name for technology in technologies}

    assert "PHP" in technology_names
    assert "Composer" in technology_names
    assert "Laravel" in technology_names
    assert "PHPUnit" in technology_names


def test_python_detector_surfaces_nested_fastapi_in_polyglot_workspace(
    tmp_path: Path,
) -> None:
    """Python detector should keep backend FastAPI visible beside a TS frontend."""

    frontend = tmp_path / "frontend"
    backend = tmp_path / "backend" / "app"
    frontend.mkdir(parents=True)
    backend.mkdir(parents=True)

    (frontend / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {"react": "^19.0.0"},
                "devDependencies": {"typescript": "^5.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (frontend / "main.ts").write_text("export const app = true;\n", encoding="utf-8")
    # Root package.json mirrors common fullstack monorepo layouts.
    (tmp_path / "package.json").write_text(
        json.dumps({"private": True, "workspaces": ["frontend", "backend"]}),
        encoding="utf-8",
    )
    (tmp_path / "frontend" / "app.js").write_text("console.log('ui');\n", encoding="utf-8")

    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["backend"]\n',
        encoding="utf-8",
    )
    (tmp_path / "backend" / "pyproject.toml").write_text(
        """
[project]
name = "backend"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.30.0",
]
[project.optional-dependencies]
dev = ["pytest>=8.0.0"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (backend / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n",
        encoding="utf-8",
    )

    repository = create_repository(tmp_path)
    python_names = {
        technology.name for technology in PythonTechnologyDetector().detect(repository)
    }
    assert "Python" in python_names
    assert "FastAPI" in python_names
    assert "pytest" in python_names

    composite = CompositeTechnologyDetector(
        detectors=[
            JavaScriptTechnologyDetector(),
            PythonTechnologyDetector(),
        ]
    )
    combined = {technology.name for technology in composite.detect(repository)}
    assert {"Python", "FastAPI", "TypeScript", "JavaScript", "Node.js"} <= combined


def test_composite_detector_combines_supported_ecosystems(
    tmp_path: Path,
) -> None:
    """Composite detector should combine results from all detectors."""

    (tmp_path / "Application.java").write_text(
        "public class Application {}",
        encoding="utf-8",
    )
    (tmp_path / "app.js").write_text(
        "console.log('hello');",
        encoding="utf-8",
    )
    (tmp_path / "index.php").write_text(
        "<?php echo 'hello';",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    repository = create_repository(tmp_path)

    detector = CompositeTechnologyDetector(
        detectors=[
            JavaTechnologyDetector(),
            JavaScriptTechnologyDetector(),
            PhpTechnologyDetector(),
            PythonTechnologyDetector(),
        ]
    )

    technologies = detector.detect(repository)

    technology_names = {technology.name for technology in technologies}

    assert "Java" in technology_names
    assert "JavaScript" in technology_names
    assert "PHP" in technology_names
    assert "Python" in technology_names
