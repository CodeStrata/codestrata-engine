"""Helpers for deriving technology facts from detections."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.models.enums import TechnologyCategory
from codestrata.models.normalized_facts import (
    TechnologyFacts,
    merge_unique_strings_case_insensitive,
)
from codestrata.models.technology import Technology


def technology_facts_from_detections(
    technologies: Sequence[Technology],
) -> TechnologyFacts:
    """Normalize detected technologies into structured technology facts."""

    programming_languages: list[str] = []
    frameworks: list[str] = []
    build_tools: list[str] = []
    test_frameworks: list[str] = []
    detected_technologies: list[str] = []

    for technology in technologies:
        name = technology.name
        detected_technologies.append(name)

        if technology.category == TechnologyCategory.LANGUAGE:
            programming_languages.append(name)
        elif technology.category == TechnologyCategory.FRAMEWORK:
            frameworks.append(name)
        elif technology.category == TechnologyCategory.BUILD_TOOL:
            build_tools.append(name)
        elif technology.category == TechnologyCategory.TESTING:
            test_frameworks.append(name)

    empty: list[str] = []

    return TechnologyFacts(
        programming_languages=merge_unique_strings_case_insensitive(
            programming_languages,
            empty,
        ),
        frameworks=merge_unique_strings_case_insensitive(frameworks, empty),
        build_tools=merge_unique_strings_case_insensitive(build_tools, empty),
        test_frameworks=merge_unique_strings_case_insensitive(
            test_frameworks,
            empty,
        ),
        detected_technologies=merge_unique_strings_case_insensitive(
            detected_technologies,
            empty,
        ),
    )
