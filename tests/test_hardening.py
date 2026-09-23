"""Regression tests for stale authorization and sensitive response handling."""

from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.models.records import Classification
from acg_agent_platform.services.store import Store


def test_saved_draft_denied_on_reclassification(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", 900)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
        source = store.source(store.principal("alice"), "KB-VPN")
        store.put_source(
            source.model_copy(update={"classification": Classification.RESTRICTED})
        )
        assert client.get(f"/api/runs/{run['id']}", headers=headers).status_code == 404


def test_validation_does_not_echo_sensitive_payload(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", 900)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/runs",
            headers={"Authorization": f"Bearer {token}"},
            json={"ticket_id": "IT-001", "secret": "never-echo"},
        )
    assert response.status_code == 422
    assert "never-echo" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
