"""Resolve full / restricted / no-export category manifests (E13.3)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.export_models import ExportCategory, parse_export_category

KNOWN_EXPORT_CATEGORIES: tuple[str, ...] = (
    ExportCategory.EVIDENCE.value,
    ExportCategory.GRAPH.value,
)

_NO_EXPORT_ALIASES = frozenset({"no-export", "no_export", "noexport", "none"})


class ExportModeError(ValueError):
    """Invalid export mode or withheld-category manifest."""


@dataclass(frozen=True, slots=True)
class ExportCategoryManifest:
    """Allowed vs withheld categories for one headless export invocation."""

    mode: ExportMode
    allowed_categories: tuple[str, ...]
    withheld_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_categories",
            tuple(sorted(set(self.allowed_categories))),
        )
        object.__setattr__(
            self,
            "withheld_categories",
            tuple(sorted(set(self.withheld_categories))),
        )
        overlap = set(self.allowed_categories) & set(self.withheld_categories)
        if overlap:
            raise ExportModeError(
                f"allowed and withheld categories overlap: {sorted(overlap)}"
            )

    @property
    def transfers(self) -> bool:
        return self.mode is not ExportMode.NONE and bool(self.allowed_categories)

    def allows(self, category: ExportCategory | str) -> bool:
        parsed = parse_export_category(category)
        if parsed is None:
            return False
        return parsed.value in self.allowed_categories

    def to_stable_dict(self) -> dict[str, Any]:
        payload = {
            "allowed_categories": list(self.allowed_categories),
            "mode": self.mode.value,
            "transfers": self.transfers,
            "withheld_categories": list(self.withheld_categories),
        }
        return {key: payload[key] for key in sorted(payload)}


def parse_export_mode(value: ExportMode | str) -> ExportMode | None:
    if isinstance(value, ExportMode):
        return value
    text = str(value).strip().lower().replace("_", "-")
    if text in _NO_EXPORT_ALIASES:
        return ExportMode.NONE
    try:
        return ExportMode(text)
    except ValueError:
        return None


def require_export_mode(value: ExportMode | str) -> ExportMode:
    parsed = parse_export_mode(value)
    if parsed is None:
        raise ExportModeError("unsupported export mode (use full, restricted, no-export)")
    return parsed


def normalize_categories(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    normalized: list[str] = []
    for item in values:
        parsed = parse_export_category(item)
        if parsed is None:
            raise ExportModeError(f"unsupported export category: {item}")
        normalized.append(parsed.value)
    return tuple(sorted(set(normalized)))


def resolve_export_manifest(
    mode: ExportMode | str,
    *,
    withheld_categories: Iterable[str] | None = None,
    allowed_categories: Iterable[str] | None = None,
) -> ExportCategoryManifest:
    """Build the withheld-category manifest for a headless export mode."""

    parsed_mode = require_export_mode(mode)
    withheld = normalize_categories(withheld_categories)
    allowed = normalize_categories(allowed_categories)
    known = set(KNOWN_EXPORT_CATEGORIES)

    if parsed_mode is ExportMode.FULL:
        if withheld:
            raise ExportModeError("full export cannot withhold categories")
        if allowed and set(allowed) != known:
            raise ExportModeError("full export must allow every known category")
        return ExportCategoryManifest(
            mode=parsed_mode,
            allowed_categories=KNOWN_EXPORT_CATEGORIES,
            withheld_categories=(),
        )

    if parsed_mode is ExportMode.NONE:
        if allowed:
            raise ExportModeError("no-export cannot allow categories")
        return ExportCategoryManifest(
            mode=parsed_mode,
            allowed_categories=(),
            withheld_categories=KNOWN_EXPORT_CATEGORIES,
        )

    if not withheld and not allowed:
        raise ExportModeError("restricted export requires a withheld-category manifest")
    if withheld and allowed:
        expected_allowed = tuple(sorted(known - set(withheld)))
        if tuple(sorted(set(allowed))) != expected_allowed:
            raise ExportModeError("restricted allowed categories must complement withheld")
    elif allowed:
        withheld = tuple(sorted(known - set(allowed)))
    else:
        allowed = tuple(sorted(known - set(withheld)))
    if not withheld:
        raise ExportModeError("restricted export must withhold at least one category")
    if set(withheld) == known:
        raise ExportModeError("withholding every category requires no-export mode")
    unknown = (set(withheld) | set(allowed)) - known
    if unknown:
        raise ExportModeError(f"unsupported export category: {sorted(unknown)}")
    return ExportCategoryManifest(
        mode=parsed_mode,
        allowed_categories=allowed,
        withheld_categories=withheld,
    )


__all__ = [
    "KNOWN_EXPORT_CATEGORIES",
    "ExportCategoryManifest",
    "ExportModeError",
    "normalize_categories",
    "parse_export_mode",
    "require_export_mode",
    "resolve_export_manifest",
]
