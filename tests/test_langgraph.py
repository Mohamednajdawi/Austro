"""Durable agent execution must survive process boundaries without repeating AI work."""

from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_graph_interrupt_survives_restart_then_executes_approved_action(
    tmp_path: Path,
) -> None:
    settings = Settings(database_path=tmp_path / "graph.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    owner = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    reviewer = {"Authorization": f"Bearer {store.issue_session('reviewer', 900)}"}
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", json={"ticket_id": "IT-001"}, headers=owner
        ).json()
        assert run["framework"] == "langgraph"
        graph = client.get(f"/api/runs/{run['id']}/graph", headers=owner).json()
        assert graph["next"] == ["human_review"]
        assert graph["paused"] is True
        proposal = client.post(f"/api/runs/{run['id']}/proposal", headers=owner).json()
    with TestClient(create_app(settings)) as restarted:
        state = restarted.get(f"/api/runs/{run['id']}/graph", headers=owner).json()
        assert state["paused"] is True
        assert (
            restarted.get(f"/api/runs/{run['id']}/graph", headers=reviewer).status_code
            == 404
        )
        base = f"/api/proposals/{proposal['id']}"
        assert (
            restarted.post(
                base + "/approve", json={"digest": proposal["digest"]}, headers=reviewer
            ).status_code
            == 200
        )
        assert restarted.post(base + "/execute", headers=owner).status_code == 200
        assert restarted.post(base + "/execute", headers=owner).status_code == 409
        state = restarted.get(f"/api/runs/{run['id']}/graph", headers=owner).json()
        assert state["next"] == []
        assert state["completed"] is True
        assert len(store.ticket(store.principal("alice"), "IT-001").notes) == 1
