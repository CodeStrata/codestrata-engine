"""Technology detector for Rust repositories."""

from __future__ import annotations

import tomllib
from pathlib import PurePosixPath
from typing import Any

from codestrata.models import Repository, Technology, TechnologyCategory


def _crate_version(declaration: object) -> str | None:
    if isinstance(declaration, str):
        text = declaration.strip()
        return text or None
    if isinstance(declaration, dict):
        version = declaration.get("version")
        if version is None:
            return None
        text = str(version).strip()
        return text or None
    return None


_FRAMEWORK_CRATES = {
    "actix-web": "Actix Web",
    "axum": "Axum",
    "dioxus": "Dioxus",
    "rocket": "Rocket",
}


class RustTechnologyDetector:
    """Detects Rust from source files and Cargo manifests."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect Rust, Cargo, and a small set of framework crates."""

        cargo_files = [
            path
            for path in repository.files
            if PurePosixPath(path).name.lower() == "cargo.toml"
        ]
        has_rust_sources = any(path.lower().endswith(".rs") for path in repository.files)
        has_lock = any(
            PurePosixPath(path).name.lower() == "cargo.lock" for path in repository.files
        )

        if not cargo_files and not has_rust_sources:
            return []

        technologies = [
            Technology(
                name="Rust",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="file_extension_or_cargo.toml",
            )
        ]
        if cargo_files or has_lock:
            technologies.append(
                Technology(
                    name="Cargo",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0 if cargo_files else 0.8,
                    source="Cargo.toml" if cargo_files else "Cargo.lock",
                )
            )

        seen: set[str] = set()
        for relative_path in cargo_files:
            for technology_name, version in self._framework_crates(repository, relative_path):
                if technology_name in seen:
                    continue
                seen.add(technology_name)
                technologies.append(
                    Technology(
                        name=technology_name,
                        version=version,
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=1.0,
                        source="Cargo.toml",
                    )
                )
        return technologies

    def _framework_crates(
        self,
        repository: Repository,
        relative_path: str,
    ) -> list[tuple[str, str | None]]:
        manifest = self._read_manifest(repository, relative_path)
        found: list[tuple[str, str | None]] = []
        for section_name in ("dependencies", "dev-dependencies"):
            section = manifest.get(section_name)
            if not isinstance(section, dict):
                continue
            for crate_name, declaration in section.items():
                technology_name = _FRAMEWORK_CRATES.get(str(crate_name))
                if technology_name is not None:
                    found.append((technology_name, _crate_version(declaration)))
        return found

    def _read_manifest(self, repository: Repository, relative_path: str) -> dict[str, Any]:
        manifest_path = repository.path / relative_path
        try:
            parsed = tomllib.loads(manifest_path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
