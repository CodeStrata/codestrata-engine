"""Validate CodeStrata regression benchmark definitions."""

from __future__ import annotations

import pytest

from tests.regression.cases import (
    REGRESSION_CASES,
    get_regression_case,
)


def test_regression_case_ids_are_unique() -> None:
    """Regression case identifiers must remain unique."""

    case_ids = [regression_case.case_id for regression_case in REGRESSION_CASES]

    assert len(case_ids) == len(set(case_ids))


def test_regression_suite_covers_mvp_languages() -> None:
    """The suite must cover Java, JavaScript, and PHP."""

    languages = {regression_case.language for regression_case in REGRESSION_CASES}

    assert {
        "java",
        "javascript",
        "php",
    }.issubset(languages)


@pytest.mark.parametrize(
    "case_id",
    [
        "java-spring-petclinic",
        "javascript-react",
        "php-laravel",
    ],
)
def test_get_regression_case(
    case_id: str,
) -> None:
    """Cases can be retrieved using stable identifiers."""

    regression_case = get_regression_case(case_id)

    assert regression_case.case_id == case_id
    assert regression_case.repository_url.startswith("https://github.com/")


def test_unknown_regression_case_raises_key_error() -> None:
    """Unknown case identifiers must fail clearly."""

    with pytest.raises(
        KeyError,
        match="Unknown regression case",
    ):
        get_regression_case("unknown-case")
