"""Regression benchmark definitions for CodeStrata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ExpectedTechnology:
    """Technology expected in a benchmark scan."""

    name: str
    category: str | None = None


@dataclass(frozen=True)
class RegressionExpectation:
    """Expected high-level results from a benchmark repository."""

    technologies: tuple[ExpectedTechnology, ...] = ()
    build_systems: tuple[str, ...] = ()
    dependency_managers: tuple[str, ...] = ()
    cicd_providers: tuple[str, ...] = ()
    required_rule_ids: tuple[str, ...] = ()
    forbidden_rule_ids: tuple[str, ...] = ()
    minimum_findings: int = 0


@dataclass(frozen=True)
class RegressionCase:
    """One repository used as an CodeStrata regression benchmark."""

    case_id: str
    language: str
    repository_url: str
    branch: str | None = None
    local_path: Path | None = None
    expectation: RegressionExpectation = field(default_factory=RegressionExpectation)


REGRESSION_CASES: tuple[RegressionCase, ...] = (
    RegressionCase(
        case_id="java-spring-petclinic",
        language="java",
        repository_url=("https://github.com/spring-projects/spring-petclinic.git"),
        expectation=RegressionExpectation(
            technologies=(
                ExpectedTechnology(
                    name="Java",
                    category="language",
                ),
                ExpectedTechnology(
                    name="Spring Boot",
                    category="framework",
                ),
                ExpectedTechnology(
                    name="Maven",
                    category="build-tool",
                ),
            ),
            build_systems=("maven",),
            dependency_managers=("maven",),
            minimum_findings=1,
        ),
    ),
    RegressionCase(
        case_id="javascript-react",
        language="javascript",
        repository_url=("https://github.com/facebook/create-react-app.git"),
        expectation=RegressionExpectation(
            technologies=(
                ExpectedTechnology(
                    name="JavaScript",
                    category="language",
                ),
                ExpectedTechnology(
                    name="React",
                    category="framework",
                ),
            ),
            dependency_managers=("npm",),
            minimum_findings=1,
        ),
    ),
    RegressionCase(
        case_id="php-laravel",
        language="php",
        repository_url=("https://github.com/laravel/laravel.git"),
        expectation=RegressionExpectation(
            technologies=(
                ExpectedTechnology(
                    name="PHP",
                    category="language",
                ),
                ExpectedTechnology(
                    name="Laravel",
                    category="framework",
                ),
                ExpectedTechnology(
                    name="Composer",
                    category="dependency-manager",
                ),
            ),
            dependency_managers=("composer",),
            minimum_findings=1,
        ),
    ),
)


def get_regression_case(
    case_id: str,
) -> RegressionCase:
    """Return a regression case by its stable identifier."""

    for regression_case in REGRESSION_CASES:
        if regression_case.case_id == case_id:
            return regression_case

    raise KeyError(f"Unknown regression case: {case_id}")
