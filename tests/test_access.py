"""Exercise identity and organizational boundaries through the public API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_session_can_read_only_its_workspace(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", lifetime=900)
    with TestClient(create_app(settings)) as client:
        headers = {"Authorization": f"Bearer {token}"}
        own = client.get("/api/tickets/IT-001", headers=headers)
        assert own.status_code == 200
        assert own.json()["id"] == "IT-001"
        assert client.get("/api/tickets/FIN-001", headers=headers).status_code == 404
        assert client.get("/api/tickets/IT-001").status_code == 401


def test_expired_session_and_disabled_user_are_rejected(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    expired = Store(settings.database_path, clock=lambda: 0.0).issue_session(
        "alice", lifetime=1
    )
    token = store.issue_session("alice", lifetime=900)
    with TestClient(create_app(settings)) as client:
        for invalid in (expired, "forged-token"):
            assert (
                client.get(
                    "/api/tickets/IT-001",
                    headers={"Authorization": f"Bearer {invalid}"},
                ).status_code
                == 401
            )
        store.set_principal_active("alice", False)
        store.seed_demo()
        assert (
            client.get(
                "/api/tickets/IT-001", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 401
        )


@pytest.mark.parametrize("ticket_id", ["FIN-001", "missing", "' OR 1=1 --"])
def test_forged_roles_do_not_grant_resource_access(
    tmp_path: Path, ticket_id: str
) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", lifetime=900)
    with TestClient(create_app(settings)) as client:
        response = client.get(
            f"/api/tickets/{ticket_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Role": "reviewer",
                "X-Workspace": "finance",
            },
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
