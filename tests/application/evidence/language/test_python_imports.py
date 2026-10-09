"""Python AST import extraction. Fixtures are not repository-independence proof."""

from __future__ import annotations

from codestrata.application.evidence.language.python_imports import (
    DISCOVERY_RULE,
    ImportDisposition,
    discover_python_source_roots,
    extract_python_imports,
    resolve_python_imports,
)
from codestrata.application.rules.prepared.import_projection import project_python_import_facts

ROOTS = ("engine/src", "platform/src")
FILES = (
    "engine/src/codestrata/app.py",
    "engine/src/codestrata/__init__.py",
    "engine/src/codestrata/application/service.py",
    "engine/src/codestrata/application/__init__.py",
    "engine/src/codestrata/rel.py",
    "platform/src/codestrata_platform/api.py",
    "platform/src/codestrata_platform/__init__.py",
    "platform/src/codestrata_platform/client.py",
)


def _project(texts: dict[str, str], **kwargs: object):
    files = tuple(texts)
    return project_python_import_facts(files, texts, source_roots=ROOTS, **kwargs)  # type: ignore[arg-type]


def test_absolute_dotted_from_relative_and_initializer_identities() -> None:
    texts = {
        "engine/src/codestrata/app.py": (
            "import codestrata_platform.api\nfrom codestrata_platform.api import App\n"
        ),
        "engine/src/codestrata/__init__.py": "",
        "engine/src/codestrata/rel.py": "from .app import thing\n",
        "engine/src/codestrata/application/__init__.py": "",
        "engine/src/codestrata/application/service.py": "import codestrata.application\n",
        "platform/src/codestrata_platform/__init__.py": "",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/client.py": "import codestrata\n",
    }
    facts = _project(texts)
    edges = {
        (edge.source, edge.target)
        for edge in facts.context.resolved_graph.edges  # type: ignore[union-attr]
        if not edge.unknown
    }
    assert ("engine/src/codestrata/app.py", "platform/src/codestrata_platform/api.py") in edges
    assert ("engine/src/codestrata/rel.py", "engine/src/codestrata/app.py") in edges
    assert (
        "engine/src/codestrata/application/service.py",
        "engine/src/codestrata/application/__init__.py",
    ) in edges
    assert (
        "platform/src/codestrata_platform/client.py",
        "engine/src/codestrata/__init__.py",
    ) in edges
    assert facts.root_discovery == "caller"
    assert facts.discovery_rule == ""
    assert facts.source_roots == ROOTS


def test_package_without_initializer_uses_the_package_directory() -> None:
    texts = {
        "engine/src/codestrata/app.py": "import codestrata_platform\n",
        "platform/src/codestrata_platform/api.py": "",
    }
    facts = _project(texts)
    targets = {
        edge.target
        for edge in facts.context.resolved_graph.edges  # type: ignore[union-attr]
        if edge.source == "engine/src/codestrata/app.py" and not edge.unknown
    }
    assert targets == {"platform/src/codestrata_platform"}


def test_distribution_name_is_not_an_import_namespace() -> None:
    texts = {
        "engine/src/codestrata/app.py": "import yaml\n",
        "engine/src/codestrata/__init__.py": "",
    }
    facts = _project(texts, external_import_names=("PyYAML",))
    record = facts.import_records[0]
    assert record.disposition is ImportDisposition.UNRESOLVED
    assert record.reason == "not_in_source_roots"
    mapped = _project(
        texts,
        external_import_names=("yaml",),
    )
    assert mapped.import_records[0].disposition is ImportDisposition.EXTERNAL
    assert mapped.context.resolved_graph.edges == ()  # type: ignore[union-attr]


def test_repository_submodule_is_not_reclassified_as_external() -> None:
    texts = {
        "engine/src/codestrata/app.py": "import codestrata.missing\n",
        "engine/src/codestrata/__init__.py": "",
    }
    facts = _project(texts, external_import_names=("codestrata",))
    assert facts.import_records[0].reason == "unresolved_submodule"
    assert facts.import_records[0].disposition is ImportDisposition.UNRESOLVED
    assert facts.context.resolved_graph.complete is False  # type: ignore[union-attr]


def test_literal_dynamic_import_resolves_and_nonliteral_blocks_completion() -> None:
    literal = {
        "engine/src/codestrata/app.py": (
            "import importlib\nimportlib.import_module('codestrata_platform.api')\n"
        ),
        "engine/src/codestrata/__init__.py": "",
        "platform/src/codestrata_platform/api.py": "",
        "platform/src/codestrata_platform/__init__.py": "",
    }
    facts = _project(literal, external_import_names=("importlib",))
    assert (
        "engine/src/codestrata/app.py",
        "platform/src/codestrata_platform/api.py",
    ) in {
        (edge.source, edge.target)
        for edge in facts.context.resolved_graph.edges  # type: ignore[union-attr]
        if not edge.unknown
    }
    dynamic = {
        "engine/src/codestrata/app.py": "import importlib\nimportlib.import_module(name)\n",
        "engine/src/codestrata/__init__.py": "",
    }
    unresolved = _project(dynamic, external_import_names=("importlib",))
    assert any(item.code == "dynamic_target_unresolved" for item in unresolved.limitations)
    assert unresolved.context.resolved_graph.complete is False  # type: ignore[union-attr]
    builtin = extract_python_imports(
        "engine/src/codestrata/app.py",
        'module = "codestrata"\n__import__(module)\n',
    )
    assert builtin[0].argument_form == "nonliteral"
    direct = extract_python_imports(
        "engine/src/codestrata/app.py",
        'from importlib import import_module\nimport_module("codestrata_platform.api")\n',
    )
    assert direct[1].dynamic_call == "importlib.import_module"
    assert direct[1].argument_form == "literal"


def test_aliased_dynamic_call_is_not_recognized() -> None:
    text = (
        "import importlib\n"
        "load = importlib.import_module\n"
        'load("codestrata_platform.api")\n'
    )
    records = extract_python_imports("engine/src/codestrata/app.py", text)
    assert all(record.kind != "dynamic" for record in records)


def test_syntax_error_keeps_location_and_two_roots_are_ambiguous() -> None:
    broken = extract_python_imports("engine/src/codestrata/app.py", "def (\n")
    assert broken[0].reason == "syntax_error"
    assert broken[0].disposition is ImportDisposition.EXTRACTION_FAILURE
    assert broken[0].line == 1
    texts = {
        "engine/src/codestrata/app.py": "import codestrata\n",
        "other/src/codestrata/app.py": "",
        "engine/src/codestrata/__init__.py": "",
        "other/src/codestrata/__init__.py": "",
    }
    facts = project_python_import_facts(
        tuple(texts),
        texts,
        source_roots=("engine/src", "other/src"),
    )
    assert any(item.code == "ambiguous_module" for item in facts.limitations)


def test_discovered_roots_and_unsupported_layout() -> None:
    files = (
        "engine/src/codestrata/app.py",
        "platform/src/codestrata_platform/api.py",
    )
    assert discover_python_source_roots(files) == ("engine/src", "platform/src")
    assert discover_python_source_roots(("src/main/python/pkg/__init__.py",)) == ()
    assert discover_python_source_roots(("lib/pkg/__init__.py",)) == ()
    missing = project_python_import_facts(
        ("lib/pkg/__init__.py",),
        {"lib/pkg/__init__.py": ""},
    )
    assert missing.root_discovery == "discovered"
    assert missing.discovery_rule == DISCOVERY_RULE
    assert missing.context.resolved_graph.complete is False  # type: ignore[union-attr]
    assert missing.limitations[0].code == "discovery_failed"
    caller = project_python_import_facts(files, {path: "" for path in files})
    assert caller.root_discovery == "discovered"
    assert caller.source_roots == ("engine/src", "platform/src")


def test_coverage_gaps_stay_incomplete() -> None:
    texts = {
        "engine/src/codestrata/app.py": "import codestrata\n",
        "engine/src/codestrata/__init__.py": "",
        "engine/src/vendor/hidden.py": "import codestrata\n",
    }
    excluded = project_python_import_facts(
        tuple(texts),
        texts,
        source_roots=("engine/src",),
    )
    assert any(item.code == "excluded_under_root" for item in excluded.limitations)
    absent = project_python_import_facts(
        ("engine/src/codestrata/app.py",),
        {"engine/src/codestrata/app.py": "import codestrata\n"},
        source_roots=("engine/src",),
        excluded_paths=("engine/src/vendor/hidden.py",),
    )
    assert any(
        item.code == "excluded_under_root" and item.path == "engine/src/vendor/hidden.py"
        for item in absent.limitations
    )
    assert absent.context is not None
    assert absent.context.resolved_graph is not None
    assert absent.context.resolved_graph.complete is False
    roots = ("engine/src", "platform/src/vendor/pkg")
    inventory = ("engine/src/codestrata/a.py",)
    texts = {"engine/src/codestrata/a.py": ""}
    descendant = project_python_import_facts(
        inventory,
        texts,
        source_roots=roots,
        pruned_directories=("engine/src/codestrata/vendor",),
    )
    assert any(
        item.code == "pruned_under_root" and item.path == "engine/src/codestrata/vendor"
        for item in descendant.limitations
    )
    ancestor = project_python_import_facts(
        inventory,
        texts,
        source_roots=roots,
        pruned_directories=("platform/src/vendor",),
    )
    assert any(
        item.code == "pruned_under_root" and item.path == "platform/src/vendor"
        for item in ancestor.limitations
    )
    assert ancestor.context is not None
    assert ancestor.context.resolved_graph is not None
    assert ancestor.context.resolved_graph.complete is False
    equal = project_python_import_facts(
        inventory,
        texts,
        source_roots=("platform/src/vendor/pkg",),
        pruned_directories=("platform/src/vendor/pkg",),
    )
    assert any(
        item.code == "pruned_under_root" and item.path == "platform/src/vendor/pkg"
        for item in equal.limitations
    )
    sibling = project_python_import_facts(
        inventory,
        texts,
        source_roots=("engine/src",),
        pruned_directories=("engine/src-extra",),
    )
    assert not any(item.code == "pruned_under_root" for item in sibling.limitations)
    caller_repository = project_python_import_facts(
        ("a.py",),
        {"a.py": ""},
        source_roots=("",),
        pruned_directories=("vendor",),
    )
    assert caller_repository.root_discovery == "caller"
    assert caller_repository.source_roots == ("",)
    assert any(
        item.code == "pruned_under_root" and item.path == "vendor"
        for item in caller_repository.limitations
    )
    assert caller_repository.context is not None
    assert caller_repository.context.resolved_graph is not None
    assert caller_repository.context.resolved_graph.complete is False
    discovered_repository = project_python_import_facts(
        ("a.py",),
        {"a.py": ""},
        pruned_directories=("vendor",),
    )
    assert discovered_repository.root_discovery == "discovered"
    assert "" in discovered_repository.source_roots
    assert any(
        item.code == "pruned_under_root" and item.path == "vendor"
        for item in discovered_repository.limitations
    )
    assert discovered_repository.context is not None
    assert discovered_repository.context.resolved_graph is not None
    assert discovered_repository.context.resolved_graph.complete is False
    outside = project_python_import_facts(
        inventory,
        texts,
        source_roots=("engine/src",),
        pruned_directories=("vendor",),
    )
    assert not any(item.code == "pruned_under_root" for item in outside.limitations)
    capped = project_python_import_facts(
        ("engine/src/codestrata/a.py",),
        {"engine/src/codestrata/a.py": ""},
        source_roots=("engine/src",),
        coverage_diagnostics_capped=True,
    )
    assert any(item.code == "coverage_diagnostics_capped" for item in capped.limitations)
    assert capped.context is not None
    assert capped.context.resolved_graph is not None
    assert capped.context.resolved_graph.complete is False
    scan_limited = project_python_import_facts(
        ("engine/src/codestrata/app.py", "engine/src/codestrata/other.py"),
        {
            "engine/src/codestrata/app.py": "",
            "engine/src/codestrata/other.py": "",
        },
        source_roots=("engine/src",),
        scan_collection_truncated=True,
    )
    assert any(
        item.code == "file_limit" and item.detail == "scan_collection_truncated"
        for item in scan_limited.limitations
    )
    unreadable = project_python_import_facts(
        ("engine/src/codestrata/app.py",),
        {},
        source_roots=("engine/src",),
    )
    assert unreadable.limitations[0].code == "unreadable"
    limited = project_python_import_facts(
        ("engine/src/codestrata/app.py", "engine/src/codestrata/other.py"),
        {
            "engine/src/codestrata/app.py": "",
            "engine/src/codestrata/other.py": "",
        },
        source_roots=("engine/src",),
        max_files=1,
    )
    assert any(item.code == "file_limit" for item in limited.limitations)
    long_text = "import codestrata\n" + ("x" * 50)
    truncated = project_python_import_facts(
        ("engine/src/codestrata/app.py", "engine/src/codestrata/__init__.py"),
        {
            "engine/src/codestrata/app.py": long_text,
            "engine/src/codestrata/__init__.py": "",
        },
        source_roots=("engine/src",),
        max_file_chars=10,
    )
    assert any(item.code == "text_limit" for item in truncated.limitations)
    for item in (excluded, unreadable, limited, truncated):
        assert item.context is not None
        assert item.context.resolved_graph is not None
        assert item.context.resolved_graph.complete is False


def test_empty_inventory_is_missing_and_records_keep_lines() -> None:
    missing = project_python_import_facts(("README.md",), {})
    assert missing.kind.value == "missing"
    assert missing.context is None
    records = extract_python_imports(
        "engine/src/codestrata/app.py",
        "import codestrata_platform.api\nfrom codestrata_platform.api import App\n",
    )
    assert records[0].line == 1
    assert records[0].module == "codestrata_platform.api"
    assert records[1].kind == "from"
    assert records[1].line == 2
    resolved = resolve_python_imports(
        records,
        files=FILES,
        source_roots=ROOTS,
        root_discovery="caller",
        discovery_rule="",
    )
    assert resolved[0].target_path == "platform/src/codestrata_platform/api.py"
    assert resolved[0].disposition is ImportDisposition.REPOSITORY
