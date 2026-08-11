"""Client boundary: lazy, injectable, non-raising, and never a global singleton."""

from __future__ import annotations

import builtins

import pytest

from codestrata.ai.provider_adapters.openai import client as client_module
from codestrata.ai.provider_adapters.openai import configuration, error_mapping
from codestrata.ai.provider_contracts.errors import ErrorCategory
from tests.ai.provider_adapters.openai import fakes


def _inputs(**kwargs: object) -> configuration.OpenAIClientInputs:
    defaults: dict[str, object] = {
        "api_key_env_name": "OPENAI_API_KEY",
        "base_url": None,
        "timeout_seconds": 60.0,
    }
    defaults.update(kwargs)
    return configuration.OpenAIClientInputs(**defaults)  # type: ignore[arg-type]


def _no_environment(_name: str) -> str | None:
    return None


def test_injected_client_is_returned_without_reading_the_environment() -> None:
    injected = fakes.FakeClient()

    def exploding_reader(_name: str) -> str | None:
        raise AssertionError("the environment must not be read for an injected client")

    resolution = client_module.resolve_client(
        _inputs(), injected_client=injected, environment_reader=exploding_reader
    )

    assert resolution.ok
    assert resolution.handle is not None
    assert resolution.handle.client is injected
    assert resolution.handle.injected is True


def test_missing_api_key_returns_a_bounded_error_instead_of_raising() -> None:
    resolution = client_module.resolve_client(_inputs(), environment_reader=_no_environment)

    assert not resolution.ok
    assert resolution.error is not None
    assert resolution.error.code == error_mapping.CODE_MISSING_API_KEY
    assert resolution.error.category is ErrorCategory.MISSING_CONFIGURATION


def test_blank_api_key_is_treated_as_missing() -> None:
    resolution = client_module.resolve_client(
        _inputs(), environment_reader=lambda _name: "   "
    )

    assert resolution.error is not None
    assert resolution.error.code == error_mapping.CODE_MISSING_API_KEY


def test_missing_openai_extra_returns_a_bounded_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)

    resolution = client_module.resolve_client(
        _inputs(), environment_reader=lambda _name: "sk-test"
    )

    assert resolution.error is not None
    assert resolution.error.code == error_mapping.CODE_MISSING_DEPENDENCY
    assert resolution.error.category is ErrorCategory.DEPENDENCY_UNAVAILABLE


def test_the_extra_is_checked_before_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing extra must not be reported as a missing key, and vice versa."""

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)

    resolution = client_module.resolve_client(_inputs(), environment_reader=_no_environment)

    assert resolution.error is not None
    assert resolution.error.code == error_mapping.CODE_MISSING_DEPENDENCY


def test_client_constructor_failure_returns_a_bounded_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    def exploding_constructor(**_kwargs: object) -> object:
        raise ValueError("invalid base_url https://private.example/v1")

    monkeypatch.setattr(openai, "OpenAI", exploding_constructor)

    resolution = client_module.resolve_client(
        _inputs(base_url="https://private.example/v1"),
        environment_reader=lambda _name: "sk-test",
    )

    assert resolution.error is not None
    assert resolution.error.code == error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED
    assert "private.example" not in resolution.error.detail


def test_constructed_client_receives_the_timeout_and_optional_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    recorded: dict[str, object] = {}

    def recording_constructor(**kwargs: object) -> object:
        recorded.update(kwargs)
        return fakes.FakeClient()

    monkeypatch.setattr(openai, "OpenAI", recording_constructor)

    resolution = client_module.resolve_client(
        _inputs(base_url="https://gw.internal", timeout_seconds=60.0),
        environment_reader=lambda _name: "sk-test",
    )

    assert resolution.ok
    assert recorded["timeout"] == 60.0
    assert recorded["base_url"] == "https://gw.internal"
    assert recorded["api_key"] == "sk-test"


def test_base_url_is_omitted_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    recorded: dict[str, object] = {}
    monkeypatch.setattr(
        openai, "OpenAI", lambda **kwargs: recorded.update(kwargs) or fakes.FakeClient()
    )

    client_module.resolve_client(_inputs(), environment_reader=lambda _name: "sk-test")

    assert "base_url" not in recorded


def test_each_resolution_builds_a_fresh_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **_kwargs: fakes.FakeClient())

    first = client_module.resolve_client(_inputs(), environment_reader=lambda _n: "sk-test")
    second = client_module.resolve_client(_inputs(), environment_reader=lambda _n: "sk-test")

    assert first.handle is not None
    assert second.handle is not None
    assert first.handle.client is not second.handle.client


def test_module_exposes_no_client_singleton() -> None:
    public = {name for name in dir(client_module) if not name.startswith("_")}

    assert not any("singleton" in name.lower() for name in public)
    assert not any(name.isupper() and "CLIENT" in name for name in public)


def test_client_handle_repr_hides_the_client_and_the_base_url() -> None:
    handle = client_module.OpenAIClientHandle(
        client=fakes.FakeClient(),
        api_key_env_name="OPENAI_API_KEY",
        base_url_configured=True,
        injected=True,
    )

    rendered = repr(handle)

    assert "FakeClient" not in rendered
    assert "base_url_configured=True" in rendered
    assert "client_present=True" in rendered


def test_default_environment_reader_reads_only_the_named_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODESTRATA_TEST_KEY_VAR", "sk-value")

    assert client_module.default_environment_reader("CODESTRATA_TEST_KEY_VAR") == "sk-value"
    assert client_module.default_environment_reader("CODESTRATA_TEST_ABSENT_VAR") is None
