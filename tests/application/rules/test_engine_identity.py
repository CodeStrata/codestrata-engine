"""Package version and pinned rule-engine catalog identity stay distinct."""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata import __version__
from codestrata.application.incremental.change_facts import build_change_cache_key
from codestrata.application.rules.effective.models import ENGINE_VERSION
from codestrata.application.rules.effective.seal import engine_digest, seal_effective_ruleset
from codestrata.domain.contracts.serialization import digest_canonical


def test_pinned_catalog_identity_is_not_the_runtime_version() -> None:
    assert ENGINE_VERSION == "0.2.1"
    assert __version__ == "0.3.1"
    assert engine_digest() == digest_canonical({"engine": ENGINE_VERSION})
    assert engine_digest() != digest_canonical({"engine": __version__})


def test_effective_ruleset_seal_does_not_hash_the_catalog_identity() -> None:
    path = Path(seal_effective_ruleset.__code__.co_filename)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "seal_effective_ruleset"
    )
    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    assert "ENGINE_VERSION" not in names


def test_new_change_cache_keys_use_the_runtime_version() -> None:
    key = build_change_cache_key(
        source_digest="aa" * 32,
        config_digest=None,
        rule_digest=None,
        feed_digest=None,
    )
    assert key.engine_version == __version__
    assert key.engine_version != ENGINE_VERSION
