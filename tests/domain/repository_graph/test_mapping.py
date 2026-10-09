"""File/component mapping identities used before E09.3."""

from __future__ import annotations

from codestrata.domain.repository_graph.mapping import (
    ROOT_COMPONENT_KEY,
    component_key_for_file,
    map_files_to_components,
)


def test_java_package_directory_is_the_component() -> None:
    key = component_key_for_file(
        "src/main/java/com/example/App.java",
        manifest_directories=(".",),
    )
    assert key == "src/main/java/com/example"


def test_manifest_directory_wins_for_nested_packages() -> None:
    key = component_key_for_file(
        "apps/one/src/index.ts",
        manifest_directories=("apps/one", "_repository"),
    )
    assert key == "apps/one"


def test_root_files_use_repository_component() -> None:
    mapping = map_files_to_components(
        ("package.json", "README.md"),
        repository_key="demo",
        manifest_directories=(ROOT_COMPONENT_KEY,),
    )
    by_path = {item.relative_path: item for item in mapping}
    assert by_path["package.json"].component_key == ROOT_COMPONENT_KEY
    assert by_path["package.json"].component_id == "repo:demo:module:_repository"
    assert by_path["package.json"].file_id == "repo:demo:file:package.json"
