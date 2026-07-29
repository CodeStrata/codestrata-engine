"""Extract concise technology/version highlights from a Repository Graph."""

from __future__ import annotations

from codestrata.domain.repository_graph import RepositoryGraph
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.reporting.modernization_models import HighlightedVersionInput

_HIGHLIGHT_NAMES = frozenset(
    {
        "java",
        "jvm",
        "spring-boot",
        "nodejs",
        "node",
    }
)
_MAX_KEY_DEPENDENCIES = 8


def build_highlighted_versions(
    repository_graph: RepositoryGraph | None,
) -> tuple[HighlightedVersionInput, ...]:
    """Return stable, concise version highlights (not a full dependency dump)."""

    if repository_graph is None:
        return ()

    highlights: list[HighlightedVersionInput] = []
    key_deps: list[HighlightedVersionInput] = []

    nodes = [
        node
        for node in repository_graph.nodes
        if node.node_type == RepositoryNodeType.DEPENDENCY.value
    ]
    nodes.sort(
        key=lambda node: (
            str(node.properties.get("ecosystem") or ""),
            str(node.properties.get("namespace") or ""),
            str(node.properties.get("name") or ""),
        )
    )

    for node in nodes:
        props = node.properties
        name = props.get("name")
        ecosystem = props.get("ecosystem")
        if not isinstance(name, str) or not isinstance(ecosystem, str):
            continue
        version = props.get("version")
        if not isinstance(version, str) or not version.strip():
            continue
        namespace = props.get("namespace")
        scope = props.get("scope")
        kind_meta = props.get("kind") if isinstance(props.get("kind"), str) else None
        # spring-boot concept nodes store kind in metadata via properties dump
        metadata_kind = None
        raw_meta = props.get("metadata")
        if isinstance(raw_meta, dict):
            maybe = raw_meta.get("kind")
            if isinstance(maybe, str):
                metadata_kind = maybe

        display = f"{namespace}:{name}" if isinstance(namespace, str) and namespace else name
        is_highlight = (
            name.lower() in _HIGHLIGHT_NAMES
            or ecosystem.lower() in {"jvm", "nodejs"}
            and name.lower() in _HIGHLIGHT_NAMES
            or metadata_kind == "spring-boot-concept"
            or kind_meta == "spring-boot-concept"
            or name.lower().startswith("spring-boot")
        )

        if name.lower() in {"java", "jvm"} or ecosystem == "jvm" and name.lower() == "java":
            highlights.append(
                HighlightedVersionInput(
                    label="Java language level",
                    value=version,
                    kind="runtime",
                    detail=display,
                )
            )
            continue
        if name.lower() in {"nodejs", "node"} or (
            ecosystem == "nodejs" and name.lower() in {"nodejs", "node"}
        ):
            highlights.append(
                HighlightedVersionInput(
                    label="Node engine",
                    value=version,
                    kind="runtime",
                    detail=display,
                )
            )
            continue
        if metadata_kind == "spring-boot-concept" or name.lower() == "spring-boot":
            highlights.append(
                HighlightedVersionInput(
                    label="Spring Boot",
                    value=version,
                    kind="framework",
                    detail=display,
                )
            )
            continue
        if is_highlight and name.lower().startswith("spring-boot"):
            # Prefer the concept node; skip starter noise when concept exists later.
            key_deps.append(
                HighlightedVersionInput(
                    label=f"Maven: {display}",
                    value=version,
                    kind="dependency",
                    detail=scope if isinstance(scope, str) else None,
                )
            )
            continue

        direct = props.get("direct")
        if direct is False:
            continue
        if ecosystem in {"maven", "npm", "jvm", "nodejs"}:
            prefix = "Maven" if ecosystem in {"maven", "jvm"} else "npm"
            key_deps.append(
                HighlightedVersionInput(
                    label=f"{prefix}: {display}",
                    value=version,
                    kind="dependency",
                    detail=scope if isinstance(scope, str) else None,
                )
            )

    # Deduplicate labels preferring first (stable) entry; keep concept highlights first.
    seen_labels: set[str] = set()
    ordered: list[HighlightedVersionInput] = []
    for item in (*highlights, *key_deps[:_MAX_KEY_DEPENDENCIES]):
        if item.label in seen_labels:
            continue
        seen_labels.add(item.label)
        ordered.append(item)
    return tuple(ordered)
