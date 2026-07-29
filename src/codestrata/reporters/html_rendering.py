"""Safe HTML rendering helpers for long values and collections."""

from __future__ import annotations

import re
from collections.abc import Sequence
from html import escape

# Collapse collections longer than this many visible items.
COLLECTION_COLLAPSE_THRESHOLD = 8

_WRAP_SPLIT_PATTERN = re.compile(r"([/:.\-_?&=])")
_WRAP_DELIMITERS = frozenset({"/", ":", ".", "-", "_", "?", "&", "="})


def escape_html(value: str) -> str:
    """Escape text for safe HTML attribute and body embedding."""

    return escape(value, quote=True)


def escape_and_wrap(value: str) -> str:
    """Escape text, then insert controlled <wbr> markers at safe delimiters.

    The original value is escaped first. Only fixed delimiter characters receive
    `<wbr>` markers so repository-controlled text cannot inject markup.
    """

    if not value:
        return ""

    pieces: list[str] = []
    for token in _WRAP_SPLIT_PATTERN.split(value):
        if not token:
            continue
        pieces.append(escape_html(token))
        if token in _WRAP_DELIMITERS:
            pieces.append("<wbr>")
    return "".join(pieces)


def wrap_table(table_html: str, *, css_class: str = "table-wrapper") -> str:
    """Wrap a table in a locally scrollable container."""

    return f'<div class="{css_class}">\n{table_html}</div>\n'


def render_value_badges(values: Sequence[str]) -> str:
    """Render short values as compact badges with safe wrapping."""

    if not values:
        return '<span class="empty">None</span>'

    badges = "".join(f'<span class="badge">{escape_and_wrap(value)}</span>' for value in values)
    return f'<div class="value-badges">{badges}</div>'


def render_value_list(values: Sequence[str]) -> str:
    """Render technical values as a wrapping vertical list."""

    if not values:
        return '<span class="empty">None</span>'

    items = "".join(
        f'<li class="technical-value">{escape_and_wrap(value)}</li>' for value in values
    )
    return f'<ul class="value-list">{items}</ul>'


def render_collection(
    values: Sequence[str],
    *,
    presentation: str = "list",
    threshold: int = COLLECTION_COLLAPSE_THRESHOLD,
) -> str:
    """Render a collection, collapsing long lists behind details/summary.

    presentation:
    - "badges" for short compact labels
    - "list" for long technical values
    """

    if not values:
        return '<span class="empty">None</span>'

    renderer = render_value_badges if presentation == "badges" else render_value_list

    if len(values) <= threshold:
        return renderer(values)

    visible = list(values[:threshold])
    hidden = list(values[threshold:])
    remaining = len(hidden)

    return (
        '<div class="expandable-collection">\n'
        f"{renderer(visible)}\n"
        "<details>\n"
        f"<summary>Show {remaining} more</summary>\n"
        f"{renderer(hidden)}\n"
        "</details>\n"
        "</div>\n"
    )
