"""Phase 4.2.1a precision-hardening regression tests."""

from __future__ import annotations

from codestrata.application.rules.architecture.helpers import (
    classification_coverage_ok,
    comparable_coupling_units,
)
from codestrata.application.rules.architecture.pack import architecture_rules
from codestrata.application.rules.architecture.view_builder import (
    build_architecture_analysis_view,
    find_directed_cycles,
    select_primary_unit,
)
from codestrata.domain.rules.architecture.ids import (
    RULE_DEPENDENCY_CYCLE,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_INVALID_DEPENDENCY_DIRECTION,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.enums import RuleResultStatus


def _ctx(view) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="repo:demo"),
        languages=LanguageInventoryView(languages=("java", "python")),
        architecture_view=view,
        policy=RuleExecutionPolicy(),
    )


def _rules():
    return {str(rule.metadata.rule_id): rule for rule in architecture_rules()}


def test_select_primary_unit_layer_aware_and_reverse_dns() -> None:
    assert (
        select_primary_unit("codestrata.application.rules.architecture")
        == "codestrata.application"
    )
    assert select_primary_unit("com.example.domain.model") == "com.example.domain"
    assert select_primary_unit("com.example.hub") == "com.example.hub"
    assert select_primary_unit("codestrata.util.helpers") == "codestrata.util"


def test_nested_package_collapse_preserves_sibling_modules() -> None:
    texts = {
        "src/codestrata/application/rules/a.py": (
            "from codestrata.domain.models import X\n"
        ),
        "src/codestrata/application/service.py": "x = 1\n",
        "src/codestrata/domain/models.py": "X = 1\n",
        "src/codestrata/domain/events.py": "Y = 1\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    ids = {unit.unit_id for unit in view.units}
    assert "codestrata.application" in ids
    assert "codestrata.domain" in ids
    assert view.raw_package_count >= view.primary_unit_count
    assert view.included_edge_count <= view.raw_edge_count


def test_parent_child_and_type_only_edges_excluded() -> None:
    texts = {
        "src/codestrata/domain/service.py": "from codestrata.domain.models.entity import E\n",
        "src/codestrata/domain/models/entity.py": "E = 1\n",
        "src/codestrata/application/service.py": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from codestrata.infrastructure.store import S\n"
            "X = 1\n"
        ),
        "src/codestrata/infrastructure/store.py": "S = 1\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    pairs = {(edge.source_unit_id, edge.target_unit_id) for edge in view.edges}
    # Nested domain.models collapses into codestrata.domain — no parent/child primary edge.
    assert ("codestrata.domain", "codestrata.domain") not in pairs
    # TYPE_CHECKING-only import to infrastructure must not create an included edge.
    assert ("codestrata.application", "codestrata.infrastructure") not in pairs
    assert view.excluded_edge_count >= 1


def test_duplicate_edges_collapsed_deterministically() -> None:
    texts = {
        "src/com/example/application/A.java": (
            "package com.example.application;\n"
            "import com.example.domain.D;\n"
            "import com.example.domain.E;\n"
            "public class A {}\n"
        ),
        "src/com/example/domain/D.java": "package com.example.domain;\npublic class D {}\n",
        "src/com/example/domain/E.java": "package com.example.domain;\npublic class E {}\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    edges = [
        edge
        for edge in view.edges
        if edge.source_unit_id == "com.example.application"
        and edge.target_unit_id == "com.example.domain"
    ]
    assert len(edges) == 1


def test_overlapping_cycles_deduped_after_collapse() -> None:
    adjacency = {
        "a": ["b"],
        "b": ["a", "c"],
        "c": ["a"],
    }
    cycles = find_directed_cycles(adjacency)
    # Shorter cycle retained; longer superset dropped.
    bodies = [cycle[:-1] for cycle in cycles]
    assert ("a", "b") in bodies
    assert ("a", "b", "c") not in bodies


def test_composition_root_not_flagged_for_direction() -> None:
    texts = {
        "src/codestrata/cli/main.py": "from codestrata.infrastructure.store import S\n",
        "src/codestrata/infrastructure/store.py": "S = 1\n",
        "src/codestrata/application/service.py": "from codestrata.domain.models import X\n",
        "src/codestrata/domain/models.py": "X = 1\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    cli = view.unit_map["codestrata.cli"]
    assert cli.role == "composition_root"
    result = _rules()[RULE_INVALID_DEPENDENCY_DIRECTION].evaluate(_ctx(view))
    subjects = [match.subject_keys for match in result.matches]
    assert all("codestrata.cli" not in keys for keys in subjects)


def test_coupling_requires_absolute_and_relative_thresholds() -> None:
    texts: dict[str, str] = {}
    # One hub with high fan-out; peers mostly idle.
    imports = "\n".join(f"import com.example.leaf{i}.L{i};" for i in range(10))
    texts["src/main/java/com/example/hub/Hub.java"] = (
        f"package com.example.hub;\n{imports}\npublic class Hub {{}}\n"
    )
    for index in range(10):
        texts[f"src/main/java/com/example/leaf{index}/L{index}.java"] = (
            f"package com.example.leaf{index};\npublic class L{index} {{}}\n"
        )
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    peers = comparable_coupling_units(view)
    assert len(peers) >= 5
    rule = architecture_rules(
        outgoing_module_threshold=8,
        minimum_module_count=5,
        relative_multiplier=2.0,
    )
    coupling = {str(item.metadata.rule_id): item for item in rule}[
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING
    ]
    matched = coupling.evaluate(_ctx(view))
    assert matched.status is RuleResultStatus.MATCHED
    # High relative multiplier should suppress when peers also fan out heavily.
    # Build balanced graph: each of 6 modules depends on 5 others.
    balanced: dict[str, str] = {}
    names = [f"m{i}" for i in range(6)]
    for name in names:
        others = [item for item in names if item != name]
        imports = "\n".join(f"import com.example.{other}.X;" for other in others)
        balanced[f"src/main/java/com/example/{name}/X.java"] = (
            f"package com.example.{name};\n{imports}\npublic class X {{}}\n"
        )
    view_b = build_architecture_analysis_view(
        relative_paths=sorted(balanced),
        file_texts=balanced,
    )
    strict = architecture_rules(
        outgoing_module_threshold=3,
        minimum_module_count=5,
        relative_multiplier=3.0,
    )
    coupling_strict = {str(item.metadata.rule_id): item for item in strict}[
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING
    ]
    # Peer median ~= 5, relative floor 15; absolute 3 but relative not met → not matched.
    assert coupling_strict.evaluate(_ctx(view_b)).status is RuleResultStatus.NOT_MATCHED


def test_extraction_vs_classification_coverage() -> None:
    texts = {
        "src/util/One.java": "package util;\nimport util.Two;\npublic class One {}\n",
        "src/util/Two.java": "package util;\npublic class Two {}\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    assert view.extraction_coverage == 1.0
    assert view.classification_coverage == 0.0
    assert classification_coverage_ok(view) is False
    assert _rules()[RULE_INVALID_DEPENDENCY_DIRECTION].evaluate_applicability(
        _ctx(view)
    ).is_applicable is False


def test_cycle_identity_stable_after_normalization() -> None:
    texts = {
        "src/codestrata/application/a.py": "from codestrata.domain import x\n",
        "src/codestrata/domain/__init__.py": "from codestrata.application import a\n",
        "src/codestrata/application/__init__.py": "a = 1\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    rule = _rules()[RULE_DEPENDENCY_CYCLE]
    first = rule.evaluate(_ctx(view))
    second = rule.evaluate(_ctx(view))
    assert [m.subject_keys for m in first.matches] == [m.subject_keys for m in second.matches]


def test_generated_paths_ignored() -> None:
    texts = {
        "src/codestrata/domain/models.py": "X = 1\n",
        "src/generated/codestrata/domain/gen.py": "from codestrata.application import a\n",
        "src/codestrata/application/a.py": "from codestrata.domain.models import X\n",
    }
    view = build_architecture_analysis_view(relative_paths=sorted(texts), file_texts=texts)
    assert all("generated" not in unit.unit_id for unit in view.units)
