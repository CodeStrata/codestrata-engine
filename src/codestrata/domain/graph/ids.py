"""Immutable identity value objects for the graph kernel."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, RootModel, model_validator


def _normalize_identity(value: Any, *, label: str) -> str:
    if isinstance(value, RootModel):
        value = value.root
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    compact = value.strip()
    if not compact:
        raise ValueError(f"{label} must not be blank")
    return compact


class GraphId(RootModel[str]):
    """Validated immutable identity for a graph snapshot."""

    model_config = ConfigDict(frozen=True)

    root: str

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: Any) -> str:
        return _normalize_identity(value, label="GraphId")

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"GraphId({self.root!r})"


class NodeId(RootModel[str]):
    """Validated immutable identity for a graph node."""

    model_config = ConfigDict(frozen=True)

    root: str

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: Any) -> str:
        return _normalize_identity(value, label="NodeId")

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"NodeId({self.root!r})"
