"""PMD analysis profile definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PmdProfile(StrEnum):
    """Named PMD analysis profiles for CodeStrata assessments."""

    FOCUSED = "focused"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


DEFAULT_PMD_PROFILE = PmdProfile.STANDARD

_DEFAULT_RULESETS = (
    "category/java/bestpractices.xml",
    "category/java/errorprone.xml",
    "category/java/design.xml",
)


@dataclass(frozen=True)
class PmdProfileDefinition:
    """Effective PMD CLI settings for one named profile."""

    profile: PmdProfile
    rulesets: tuple[str, ...]
    minimum_priority: int
    description: str


PROFILE_DEFINITIONS: dict[PmdProfile, PmdProfileDefinition] = {
    PmdProfile.FOCUSED: PmdProfileDefinition(
        profile=PmdProfile.FOCUSED,
        rulesets=(
            "category/java/errorprone.xml",
            "category/java/security.xml",
            "category/java/design.xml",
        ),
        minimum_priority=3,
        description=(
            "Executive/customer assessment: correctness, security, and significant "
            "design risks with lower stylistic noise."
        ),
    ),
    PmdProfile.STANDARD: PmdProfileDefinition(
        profile=PmdProfile.STANDARD,
        rulesets=_DEFAULT_RULESETS,
        minimum_priority=3,
        description=(
            "Normal modernization assessment: correctness, error-prone issues, "
            "maintainability, and selected best practices."
        ),
    ),
    PmdProfile.COMPREHENSIVE: PmdProfileDefinition(
        profile=PmdProfile.COMPREHENSIVE,
        rulesets=_DEFAULT_RULESETS,
        minimum_priority=5,
        description=(
            "Full configured PMD evidence including LOW-priority conventions "
            "and style-oriented findings."
        ),
    ),
}


def parse_pmd_profile(value: str | PmdProfile | None) -> PmdProfile:
    """Parse and validate a PMD profile name."""

    if value is None:
        return DEFAULT_PMD_PROFILE
    if isinstance(value, PmdProfile):
        return value
    compact = value.strip().lower()
    try:
        return PmdProfile(compact)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in PmdProfile)
        raise ValueError(f"Invalid PMD profile {value!r}. Expected one of: {allowed}") from exc


def resolve_pmd_profile_definition(
    profile: str | PmdProfile | None = None,
    *,
    configured_rulesets: list[str] | None = None,
) -> PmdProfileDefinition:
    """Resolve the effective profile definition.

    Comprehensive may honor explicitly configured rulesets when provided.
    Focused and standard always use the profile ruleset pack so noise stays controlled.
    """

    resolved = parse_pmd_profile(profile)
    definition = PROFILE_DEFINITIONS[resolved]
    if resolved == PmdProfile.COMPREHENSIVE and configured_rulesets:
        return PmdProfileDefinition(
            profile=definition.profile,
            rulesets=tuple(configured_rulesets),
            minimum_priority=definition.minimum_priority,
            description=definition.description,
        )
    return definition
