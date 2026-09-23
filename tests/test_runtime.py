"""Exercise failure boundaries and the actual loopback ASGI server."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.models.workflow import Envelope, Stage
from acg_agent_platform.services.gateway import (
    BaseModelAdapter,
    BasePolicy,
    FakeModel,
    PolicyDenied,
)
from acg_agent_platform.services.store import Store


def prepare(tmp_path: Path) -> tuple[Settings, Store, dict[str, str]]:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    return (
        settings,
        store,
        {"Authorization": f"Bearer {store.issue_session('alice', 900)}"},
    )


class RejectOutput(BasePolicy):
    def inspect(self, envelope: Envelope) -> None:
        if '"draft":' in envelope.text:
            raise PolicyDenied


def test_model_output_is_inspected_before_exposure(tmp_path: Path) -> None:
    settings, _, headers = prepare(tmp_path)
    with TestClient(create_app(settings, policy=RejectOutput())) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        )
    assert response.json()["state"] == "blocked"
    assert response.json()["draft"] == ""
    assert response.json()["model_calls"] == 2


class RevokingModel(BaseModelAdapter):
    name = "fake/revocation-test"

    def __init__(self, store: Store) -> None:
        self.store = store

    def infer(self, envelope: Envelope) -> str:
        if envelope.stage == Stage.DRAFT:
            source = self.store.source(self.store.principal("alice"), "KB-VPN")
            self.store.put_source(source.model_copy(update={"active": False}))
        return FakeModel().infer(envelope)


def test_revocation_during_generation_discards_draft(tmp_path: Path) -> None:
    settings, store, headers = prepare(tmp_path)
    with TestClient(create_app(settings, model=RevokingModel(store))) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
    assert run["state"] == "blocked"
    assert run["draft"] == ""


def test_audit_storage_failure_does_not_return_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, _, headers = prepare(tmp_path)

    def fail_save(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("sensitive-database-path")

    monkeypatch.setattr(Store, "save_run", fail_save)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        )
    assert response.status_code == 503
    assert "sensitive-database-path" not in response.text


def test_actual_loopback_server_can_authenticate_and_draft(tmp_path: Path) -> None:
    settings, _, headers = prepare(tmp_path)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = os.environ.copy()
    environment.update(DATABASE_PATH=str(settings.database_path), PORT=str(port))
    process = subprocess.Popen(
        [sys.executable, "-m", "acg_agent_platform", "serve"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("Loopback server exited before startup")
            try:
                with urlopen(base + "/health", timeout=0.5) as response:
                    assert json.load(response)["scope"] == "synthetic-demo"
                break
            except URLError:
                time.sleep(0.1)
        else:
            pytest.fail("Loopback server did not start")
        request = Request(
            base + "/api/runs",
            method="POST",
            data=b'{"ticket_id":"IT-001","language":"en"}',
            headers={**headers, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            run = json.load(response)
            assert response.status == 201
            assert run["state"] == "awaiting_review"
            assert run["model_calls"] == 2
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
