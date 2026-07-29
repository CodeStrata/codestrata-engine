"""Phase 5.17 PHP support unit tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.dependency.composer_collector import (
    collect_composer_dependency_bundle,
)
from codestrata.application.evidence.language.providers.php_provider import (
    PhpLanguageEvidenceProvider,
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
from codestrata.services.detectors.php_technology_detector import PhpTechnologyDetector
from codestrata.services.repository_graph.extractors.composer_parser import (
    parse_composer_json_dependencies,
)


def test_php_detector_frameworks(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text(
        """
        {
          "require": {
            "php": "^8.2",
            "laravel/framework": "^11.0",
            "codeigniter4/framework": "^4.5",
            "laminas/laminas-mvc": "^3.7",
            "symfony/framework-bundle": "^7.0"
          },
          "require-dev": {
            "phpunit/phpunit": "^11.0"
          }
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "app.php").write_text("<?php\n", encoding="utf-8")
    repository = Repository(
        name="php-sample",
        path=tmp_path,
        files=["composer.json", "app.php", "artisan"],
    )
    technologies = PhpTechnologyDetector().detect(repository)
    names = {item.name for item in technologies}
    assert "PHP" in names
    assert "Composer" in names
    assert "Laravel" in names
    assert "Symfony" in names
    assert "CodeIgniter" in names
    assert "Laminas" in names
    assert "PHPUnit" in names


def test_composer_metadata_and_graph_parser(tmp_path: Path) -> None:
    manifest = tmp_path / "composer.json"
    payload = """
    {
      "require": {
        "php": "^8.2",
        "laravel/framework": "^11.0"
      },
      "require-dev": {
        "phpunit/phpunit": "^11.0"
      }
    }
    """
    manifest.write_text(payload, encoding="utf-8")
    repository = Repository(
        name="php-deps",
        path=tmp_path,
        files=["composer.json"],
    )
    result = DependencyMetadataAnalyzer().analyze(repository, technologies=[])
    deps = result.facts.dependencies.dependencies if result.facts.dependencies else []
    names = {item.name for item in deps}
    assert "laravel/framework" in names
    assert "phpunit/phpunit" in names
    assert "php" not in names
    assert all(item.ecosystem == "composer" for item in deps)

    parsed = parse_composer_json_dependencies(payload.encode("utf-8"), source_file="composer.json")
    assert any(item.name == "framework" and item.namespace == "laravel" for item in parsed)


def test_php_import_extraction_and_units() -> None:
    text = """<?php
namespace App\\Controllers;
use App\\Models\\User;
require 'bootstrap.php';
"""
    imports = extract_imports("src/App/Controllers/UserController.php", text)
    assert "App.Models.User" in imports or "App.Models" in {
        item.rsplit(".", 1)[0] if "." in item else item for item in imports
    }
    facts = collect_raw_package_facts(
        relative_paths=[
            "src/App/Controllers/UserController.php",
            "src/Domain/Models/User.php",
        ],
        file_texts={
            "src/App/Controllers/UserController.php": (
                "<?php\nnamespace App\\Controllers;\n"
                "use Domain\\Models\\User;\n"
                "class UserController {}\n"
            ),
            "src/Domain/Models/User.php": (
                "<?php\nnamespace Domain\\Models;\n"
                "use Illuminate\\Database\\Eloquent\\Model;\n"
                "class User extends Model {}\n"
            ),
        },
        language_filter="php",
    )
    assert facts.files_parsed >= 2
    assert any(hit.framework == "laravel" for hit in facts.framework_hits)
    assert facts.resolved_edges or facts.package_files


def test_php_language_evidence_provider() -> None:
    provider = PhpLanguageEvidenceProvider()
    context = LanguageEvidenceContext(
        repository_id="sample",
        relative_paths=["src/App/Models/User.php"],
        file_texts={
            "src/App/Models/User.php": (
                "<?php\nnamespace App\\Models;\n"
                "use Illuminate\\Database\\Eloquent\\Model;\n"
                "class User extends Model {}\n"
            )
        },
        configuration={"fingerprint": "test"},
    )
    assert provider.evaluate_applicability(context).status.value == "applicable"
    result = provider.collect(context)
    assert result.status.value in {"succeeded", "partially_succeeded"}


def test_composer_dependency_evidence() -> None:
    bundle = collect_composer_dependency_bundle(
        relative_paths=["composer.json"],
        file_texts={
            "composer.json": (
                '{"require":{"laravel/framework":"^11.0"},'
                '"require-dev":{"phpunit/phpunit":"^11.0"}}'
            )
        },
        ignore_path_markers=("/vendor/",),
    )
    assert bundle.ecosystem is DependencyEcosystem.COMPOSER
    identities = {item.normalized_identity for item in bundle.declarations}
    assert "laravel/framework" in identities
    assert "phpunit/phpunit" in identities
