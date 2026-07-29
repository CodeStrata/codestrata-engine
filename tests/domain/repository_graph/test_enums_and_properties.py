"""Tests for Repository Graph enums and typed property models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.domain.repository_graph import (
    CallableProperties,
    DependencyProperties,
    DependencyScope,
    FileProperties,
    ModuleProperties,
    NamespaceProperties,
    RepositoryCallableKind,
    RepositoryFileKind,
    RepositoryNodeType,
    RepositoryProperties,
    RepositoryRelationshipType,
    RepositoryTypeKind,
    TypeProperties,
)


def test_enum_vocabularies() -> None:
    assert set(RepositoryNodeType) == {
        RepositoryNodeType.REPOSITORY,
        RepositoryNodeType.MODULE,
        RepositoryNodeType.FILE,
        RepositoryNodeType.NAMESPACE,
        RepositoryNodeType.TYPE,
        RepositoryNodeType.CALLABLE,
        RepositoryNodeType.DEPENDENCY,
    }
    assert set(RepositoryRelationshipType) == {
        RepositoryRelationshipType.CONTAINS,
        RepositoryRelationshipType.DECLARES,
        RepositoryRelationshipType.DEPENDS_ON,
        RepositoryRelationshipType.CALLS,
    }
    assert RepositoryFileKind.SOURCE == "source"
    assert RepositoryTypeKind.INTERFACE == "interface"
    assert RepositoryCallableKind.METHOD == "method"
    assert DependencyScope.COMPILE == "compile"


def test_property_models_valid_construction_and_serialization() -> None:
    repo = RepositoryProperties(name="petclinic", branch="main")
    assert repo.to_properties() == {
        "name": "petclinic",
        "source_type": None,
        "branch": "main",
        "revision": None,
        "source_location": None,
    }

    module = ModuleProperties(name="app", path="modules/app", build_system="maven")
    assert module.to_properties()["path"] == "modules/app"

    file_props = FileProperties(
        path="src/App.java",
        file_kind=RepositoryFileKind.SOURCE,
        language="java",
        size_bytes=12,
        generated=False,
    )
    payload = file_props.to_properties()
    assert payload["file_kind"] == "source"
    assert payload["size_bytes"] == 12
    assert isinstance(payload, dict)

    ns = NamespaceProperties(qualified_name="com.example", language="java")
    assert ns.to_properties()["qualified_name"] == "com.example"

    type_props = TypeProperties(
        name="App",
        qualified_name="com.example.App",
        type_kind=RepositoryTypeKind.CLASS,
        abstract=True,
    )
    assert type_props.to_properties()["type_kind"] == "class"

    callable_props = CallableProperties(
        name="run",
        qualified_signature="com.example.App#run()",
        callable_kind=RepositoryCallableKind.METHOD,
        static=True,
    )
    assert callable_props.to_properties()["static"] is True

    dep = DependencyProperties(
        ecosystem="maven",
        name="spring-core",
        namespace="org.springframework",
        version="6.1.0",
        scope=DependencyScope.COMPILE,
        direct=True,
        source_file="pom.xml",
    )
    assert dep.to_properties()["version"] == "6.1.0"
    assert dep.to_properties()["source_file"] == "pom.xml"


def test_property_models_reject_blank_and_negative_size() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        RepositoryProperties(name=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        RepositoryProperties(name="ok", branch=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        ModuleProperties(name="ok", build_system="")
    with pytest.raises(ValidationError):
        FileProperties(path="a.java", file_kind=RepositoryFileKind.SOURCE, size_bytes=-1)
    with pytest.raises(ValidationError, match="must not be blank"):
        NamespaceProperties(qualified_name=" ")
    with pytest.raises(ValidationError, match="must not be blank"):
        TypeProperties(
            name="A",
            qualified_name="a.A",
            type_kind=RepositoryTypeKind.CLASS,
            visibility=" ",
        )
    with pytest.raises(ValidationError, match="must not be blank"):
        DependencyProperties(ecosystem="maven", name=" ")
