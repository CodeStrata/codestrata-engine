"""Composite detector for supported CodeStrata technologies."""

from collections.abc import Iterable
from typing import Protocol

from codestrata.models import Repository, Technology


class LanguageTechnologyDetector(Protocol):
    """Contract implemented by language-specific detectors."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect technologies in a repository."""
        ...


class CompositeTechnologyDetector:
    """Runs multiple detectors and combines their results."""

    def __init__(
        self,
        detectors: Iterable[LanguageTechnologyDetector],
    ) -> None:
        self._detectors = list(detectors)

    def detect(self, repository: Repository) -> list[Technology]:
        """Run all configured detectors and remove duplicate technologies."""

        technologies: list[Technology] = []

        for detector in self._detectors:
            technologies.extend(detector.detect(repository))

        return self._deduplicate(technologies)

    def _deduplicate(
        self,
        technologies: list[Technology],
    ) -> list[Technology]:
        """Remove duplicate technologies by name and category."""

        unique_technologies: dict[
            tuple[str, str],
            Technology,
        ] = {}

        for technology in technologies:
            key = (
                technology.name.lower(),
                technology.category.value,
            )

            existing = unique_technologies.get(key)

            if existing is None:
                unique_technologies[key] = technology
                continue

            existing_confidence = existing.confidence or 0.0
            new_confidence = technology.confidence or 0.0

            if new_confidence > existing_confidence:
                unique_technologies[key] = technology

        return sorted(
            unique_technologies.values(),
            key=lambda technology: (
                technology.category.value,
                technology.name.lower(),
            ),
        )
