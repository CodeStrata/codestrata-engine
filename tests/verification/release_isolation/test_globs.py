"""GitHub glob and push-pattern extraction fixtures."""

from __future__ import annotations

from verification.release_isolation.globs import (
    extract_push_branch_patterns,
    github_ref_matches,
)

CI = """
name: ci
on:
  pull_request:
  push:
    branches:
      - main
      - develop
      - "release/**"
permissions:
  contents: read
"""

MAIN_ONLY = """
name: ci
on:
  push:
    branches:
      - main
"""

UNFILTERED = """
name: ci
on:
  push:
permissions:
  contents: read
"""

NO_PUSH = """
name: ci
on:
  pull_request:
"""

INLINE = """
name: ci
on: [push, pull_request]
"""

STAR = """
name: ci
on:
  push:
    branches:
      - "release/*"
"""


def test_double_star_matches_integration_and_nested() -> None:
    assert github_ref_matches("release/**", "release/engine-next")
    assert github_ref_matches("release/**", "release/foo/bar")
    assert not github_ref_matches("release/*", "release/foo/bar")
    assert github_ref_matches("release/*", "release/engine-next")
    assert not github_ref_matches("release/**", "main")
    assert not github_ref_matches("release/**", "engine/E00.3-isolation")


def test_extracts_quoted_release_glob() -> None:
    assert extract_push_branch_patterns(CI) == ("main", "develop", "release/**")


def test_missing_push_is_none() -> None:
    assert extract_push_branch_patterns(NO_PUSH) is None


def test_unfiltered_push_is_empty_tuple() -> None:
    assert extract_push_branch_patterns(UNFILTERED) == ()


def test_inline_on_list_is_unfiltered_push() -> None:
    assert extract_push_branch_patterns(INLINE) == ()


def test_main_only_does_not_include_release_glob() -> None:
    assert extract_push_branch_patterns(MAIN_ONLY) == ("main",)
    assert extract_push_branch_patterns(STAR) == ("release/*",)
