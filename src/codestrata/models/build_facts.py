from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field


class BuildFacts(BaseModel):
    """Structured facts about repository build systems and configuration."""

    build_systems: list[str] = Field(default_factory=list)
    build_files: list[str] = Field(default_factory=list)
    wrapper_files: list[str] = Field(default_factory=list)
    lock_files: list[str] = Field(default_factory=list)

    multiple_build_systems: bool = False

    multi_module: bool = False
    modules: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)

    packaging_types: list[str] = Field(default_factory=list)

    java_source_versions: list[str] = Field(default_factory=list)
    java_target_versions: list[str] = Field(default_factory=list)

    inferred_commands: list[str] = Field(default_factory=list)

    def merge(self, other: BuildFacts) -> Self:
        """Merge independently produced build facts."""

        return self.model_copy(
            update={
                "build_systems": _merge_unique(
                    self.build_systems,
                    other.build_systems,
                ),
                "build_files": _merge_unique(
                    self.build_files,
                    other.build_files,
                ),
                "wrapper_files": _merge_unique(
                    self.wrapper_files,
                    other.wrapper_files,
                ),
                "lock_files": _merge_unique(
                    self.lock_files,
                    other.lock_files,
                ),
                "multiple_build_systems": (
                    self.multiple_build_systems
                    or other.multiple_build_systems
                    or len(
                        _merge_unique(
                            self.build_systems,
                            other.build_systems,
                        )
                    )
                    > 1
                ),
                "multi_module": self.multi_module or other.multi_module,
                "modules": _merge_unique(
                    self.modules,
                    other.modules,
                ),
                "plugins": _merge_unique(
                    self.plugins,
                    other.plugins,
                ),
                "packaging_types": _merge_unique(
                    self.packaging_types,
                    other.packaging_types,
                ),
                "java_source_versions": _merge_unique(
                    self.java_source_versions,
                    other.java_source_versions,
                ),
                "java_target_versions": _merge_unique(
                    self.java_target_versions,
                    other.java_target_versions,
                ),
                "inferred_commands": _merge_unique(
                    self.inferred_commands,
                    other.inferred_commands,
                ),
            }
        )


def _merge_unique(left: list[str], right: list[str]) -> list[str]:
    """Merge lists while preserving their original order."""

    return list(dict.fromkeys([*left, *right]))
