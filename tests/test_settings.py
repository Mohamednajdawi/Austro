"""Startup must reject unsafe deployment modes before serving requests."""

import pytest
from pydantic import ValidationError

from acg_agent_platform.config import Settings


def test_external_inference_cannot_be_enabled() -> None:
    with pytest.raises(ValidationError):
        Settings(allow_external_inference=True)


@pytest.mark.parametrize(
    "key,value",
    [
        ("APP_MODE", "production"),
        ("MODEL_PROVIDER", "external"),
        ("ALLOW_PRODUCTION_WRITES", "true"),
        ("ENABLE_TELEMETRY", "true"),
        ("HOST", "0.0.0.0"),
        ("MAX_CONTEXT_CHARS", "0"),
        ("ALLOW_EXTERNAL_INFERENCE", "maybe"),
    ],
)
def test_unsafe_environment_rejected(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError):
        Settings()


def test_secrets_are_not_in_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "synthetic-secret-not-for-logs")
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "synthetic-secret-not-for-logs" not in str(exc.value)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://localhost:11435",
        "http://127.0.0.1:11435/redirect",
        "http://user:pass@127.0.0.1:11435",
        "http://127.0.0.1:11435?remote=true",
    ],
)
def test_model_endpoint_cannot_escape_loopback(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(ollama_url=url)
