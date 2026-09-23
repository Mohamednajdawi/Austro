"""Validate deployment settings once without importing unrelated secrets."""

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    SYNTHETIC = "synthetic-demo"


class Provider(StrEnum):
    FAKE = "fake"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, extra="forbid", frozen=True, hide_input_in_errors=True
    )

    app_mode: Mode = Mode.SYNTHETIC
    model_provider: Provider = Provider.FAKE
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    database_path: Path = Path("runtime/demo.sqlite3")
    allow_external_inference: bool = False
    allow_production_writes: bool = False
    enable_telemetry: bool = False
    session_seconds: int = Field(default=900, ge=1, le=3600)
    max_context_chars: int = Field(default=20000, ge=1, le=20000)
    max_sources: int = Field(default=5, ge=1, le=5)
    ollama_url: str = "http://127.0.0.1:11435"
    ollama_model: str = Field(default="qwen2.5:1.5b", pattern=r"^[a-zA-Z0-9_.:-]+$")
    model_timeout: float = Field(default=120, ge=1, le=300)
    approval_seconds: int = Field(default=900, ge=1, le=3600)
    wo_instance: str = ""
    wo_api_key: SecretStr = SecretStr("")
    model_base_url: str = ""
    model_api_key: SecretStr = SecretStr("")
    oidc_issuer: str = ""
    oidc_client_id: str = ""

    @model_validator(mode="after")
    def require_offline_demo(self) -> Self:
        from urllib.parse import urlsplit

        url = urlsplit(self.ollama_url)
        if (
            url.scheme != "http"
            or url.hostname != "127.0.0.1"
            or url.port is None
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError("Model service must use an explicit loopback HTTP port")
        if "cloud" in self.ollama_model.lower():
            raise ValueError("Cloud models are not allowed")
        if self.host != "127.0.0.1":
            raise ValueError("Only IPv4 loopback binding is supported")
        if any(
            (
                self.allow_external_inference,
                self.allow_production_writes,
                self.enable_telemetry,
            )
        ):
            raise ValueError("External processing, telemetry and real writes disabled")
        if any(
            (
                self.wo_instance,
                self.wo_api_key.get_secret_value(),
                self.model_base_url,
                self.model_api_key.get_secret_value(),
                self.oidc_issuer,
                self.oidc_client_id,
            )
        ):
            raise ValueError("Live integration configuration is not supported")
        return self
