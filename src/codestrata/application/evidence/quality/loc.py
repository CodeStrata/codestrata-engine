"""Physical nonblank noncomment line counting (nloc.v1)."""

from __future__ import annotations

from functools import lru_cache

from codestrata.application.evidence.quality.tokenize import classify_lines, tokenize_source


def physical_line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


@lru_cache(maxsize=1024)
def nloc_line_numbers(text: str, *, language: str) -> frozenset[int]:
    """Line numbers that contain a non-comment, non-blank source token."""

    tokens = tokenize_source(text, language=language)
    return classify_lines(tokens)


def nloc_count(text: str, *, language: str) -> int:
    return len(nloc_line_numbers(text, language=language))


def nloc_in_span(text: str, *, language: str, line_start: int, line_end: int) -> int:
    lines = nloc_line_numbers(text, language=language)
    return sum(1 for line in lines if line_start <= line <= line_end)


__all__ = ["nloc_count", "nloc_in_span", "nloc_line_numbers", "physical_line_count"]
