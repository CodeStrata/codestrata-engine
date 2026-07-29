"""Tests for deterministic Repository Graph node identity construction."""

from __future__ import annotations

import pytest

from codestrata.domain.repository_graph import RepositoryNodeIdFactory


def test_identity_factory_deterministic_outputs() -> None:
    first = RepositoryNodeIdFactory("petclinic")
    second = RepositoryNodeIdFactory("petclinic")

    assert first.repository() == second.repository()
    assert str(first.repository()) == "repo:petclinic"
    assert str(first.module("app")) == "repo:petclinic:module:app"
    assert str(first.module("services/orders")) == "repo:petclinic:module:services/orders"
    assert str(first.file("src/App.java")) == "repo:petclinic:file:src/App.java"
    assert str(first.namespace("com.example")) == "repo:petclinic:namespace:com.example"
    assert str(first.type("com.example.App")) == "repo:petclinic:type:com.example.App"


def test_file_path_normalization_and_rejection() -> None:
    factory = RepositoryNodeIdFactory("petclinic")
    assert str(factory.file(r"src\main\App.java")) == "repo:petclinic:file:src/main/App.java"
    assert str(factory.file("./src/App.java")) == "repo:petclinic:file:src/App.java"

    with pytest.raises(ValueError, match="repository-relative"):
        factory.file("/abs/App.java")
    with pytest.raises(ValueError, match="repository-relative"):
        factory.file("C:/abs/App.java")
    with pytest.raises(ValueError, match=r"\.\."):
        factory.file("../secret/App.java")
    with pytest.raises(ValueError, match=r"\.\."):
        factory.file("src/../../etc/passwd")


def test_callable_overloads_and_dependency_identity() -> None:
    factory = RepositoryNodeIdFactory("petclinic")
    one = factory.callable(qualified_owner="com.example.App", signature="run()")
    two = factory.callable(qualified_owner="com.example.App", signature="run(String)")
    assert one != two
    assert "#run()" in str(one)
    assert "#run(String)" in str(two)

    dep_v1 = factory.dependency(
        ecosystem="maven",
        name="spring-core",
        namespace="org.springframework",
    )
    dep_v2 = factory.dependency(
        ecosystem="maven",
        name="spring-core",
        namespace="org.springframework",
    )
    assert dep_v1 == dep_v2
    assert str(dep_v1) == ("repo:petclinic:dependency:maven:org.springframework:spring-core")

    npm = factory.dependency(ecosystem="npm", name="lodash", namespace=None)
    assert str(npm) == "repo:petclinic:dependency:npm:_:lodash"
    assert npm != factory.dependency(
        ecosystem="maven",
        name="lodash",
        namespace=None,
    )


def test_blank_and_credential_like_keys_rejected() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        RepositoryNodeIdFactory(" ")
    with pytest.raises(ValueError, match="credential|URL"):
        RepositoryNodeIdFactory("https://example.com/repo")
    with pytest.raises(ValueError, match="credential|URL"):
        RepositoryNodeIdFactory("user@host")
    with pytest.raises(ValueError, match=":"):
        RepositoryNodeIdFactory("org:repo")

    factory = RepositoryNodeIdFactory("petclinic")
    with pytest.raises(ValueError, match="must not be blank"):
        factory.module(" ")
    with pytest.raises(ValueError, match="must not be blank"):
        factory.namespace(" ")
    with pytest.raises(ValueError, match="must not be blank"):
        factory.callable(qualified_owner="Owner", signature=" ")
    with pytest.raises(ValueError, match="must not be blank"):
        factory.dependency(ecosystem=" ", name="x")
