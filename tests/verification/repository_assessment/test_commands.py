"""SV.4 command helper tests."""

from __future__ import annotations

import pytest

from verification.repository_assessment.commands import (
    assert_no_ai_flag,
    assessment_environ,
    canonical_assess_argv,
)


def test_canonical_argv_includes_no_ai() -> None:
    argv = canonical_assess_argv()
    assert argv[0] == "assess"
    assert "--no-ai" in argv
    assert "--with-ai" not in argv


def test_assert_no_ai_flag() -> None:
    assert_no_ai_flag(("assess", "--no-ai"))
    with pytest.raises(AssertionError):
        assert_no_ai_flag(("assess", "--with-ai"))


def test_assessment_environ_scrubs_secrets() -> None:
    env = assessment_environ(
        {
            "PATH": "/usr/bin",
            "OPENAI_API_KEY": "sk-test",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "PYTHONPATH": "/leak",
        }
    )
    assert "OPENAI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "PYTHONPATH" not in env
    assert env.get("CI") == "1"
