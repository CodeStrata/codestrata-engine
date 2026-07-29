"""Safely load and normalize YAML-based CI/CD pipeline files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class YamlPipelineLoader:
    """Load YAML pipeline files into normalized dictionaries."""

    def load(
        self,
        pipeline_path: Path,
    ) -> dict[str, Any]:
        """Load and normalize a YAML pipeline file.

        Missing, unreadable, invalid, or non-mapping YAML documents return
        an empty dictionary so pipeline analysis does not interrupt the
        repository scan.
        """

        if not pipeline_path.is_file():
            return {}

        try:
            content = pipeline_path.read_text(encoding="utf-8")
            raw_data = yaml.safe_load(content)
        except (
            OSError,
            UnicodeDecodeError,
            yaml.YAMLError,
        ):
            return {}

        if not isinstance(raw_data, Mapping):
            return {}

        return self.mapping(raw_data)

    def mapping(
        self,
        value: object,
    ) -> dict[str, Any]:
        """Normalize a mapping into a string-keyed dictionary.

        PyYAML follows YAML 1.1 behavior and may interpret an unquoted
        GitHub Actions `on` key as the boolean value True. Normalize that
        key back to `on`.
        """

        if not isinstance(value, Mapping):
            return {}

        normalized_mapping: dict[str, Any] = {}

        for key, item in value.items():
            normalized_key = self._normalize_key(key)
            normalized_mapping[normalized_key] = item

        return normalized_mapping

    def string_list(
        self,
        value: object,
    ) -> list[str]:
        """Normalize a string or list of strings."""

        if isinstance(value, str):
            normalized_value = value.strip()
            return [normalized_value] if normalized_value else []

        if not isinstance(value, list):
            return []

        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def optional_string(
        self,
        value: object,
    ) -> str | None:
        """Return a non-empty normalized string or None."""

        if not isinstance(value, str):
            return None

        normalized_value = value.strip()

        return normalized_value or None

    def _normalize_key(
        self,
        key: object,
    ) -> str:
        """Normalize YAML mapping keys.

        GitHub Actions commonly uses the unquoted key `on`. Under YAML 1.1,
        PyYAML may parse this as the boolean key True.
        """

        if key is True:
            return "on"

        if key is False:
            return "off"

        return str(key)
