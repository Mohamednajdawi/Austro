"""Enforce browser origin boundaries and mutation rollback."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.approvals import Approvals
from acg_agent_platform.services.store import Store


def test_cross_origin_mutation_and_untrusted_host_denied(tmp_path: Path) -> None:
    with TestClient(
        create_app(Settings(database_path=tmp_path / "demo.sqlite3"))
    ) as client:
        response = client.post(
            "/api/tickets",
            headers={"Origin": "https://evil.example"},
            json={"title": "Ticket", "description": "Some description"},
        )
        assert response.status_code == 403
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/").status_code == 200


def test_execution_rolls_back_if_audit_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    alice = store.principal("alice")
    reviewer = store.principal("reviewer")
    headers = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
    service = Approvals(store.path)
    proposal = service.propose(alice, run["id"])
    service.approve(reviewer, proposal.id, proposal.digest)

    def unavailable(*args: object) -> None:
        raise sqlite3.OperationalError("Simulated audit write outage")

    monkeypatch.setattr(service, "_save", unavailable)
    with pytest.raises(sqlite3.OperationalError):
        service.execute(alice, proposal.id)
    assert not store.ticket(alice, "IT-001").notes
    assert service.get(alice, proposal.id).state.value == "approved"
