"""Exercise exact-action approval and a real local sandbox mutation."""

from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_review_then_execute_appends_exactly_one_note(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "sandbox.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    alice = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    reviewer = {"Authorization": f"Bearer {store.issue_session('reviewer', 900)}"}
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=alice, json={"ticket_id": "IT-001"}
        ).json()
        response = client.post(f"/api/runs/{run['id']}/proposal", headers=alice)
        assert response.status_code == 201
        proposal = response.json()
        endpoint = f"/api/proposals/{proposal['id']}"
        assert client.post(endpoint + "/execute", headers=alice).status_code == 409
        assert (
            client.post(
                endpoint + "/approve",
                headers=alice,
                json={"digest": proposal["digest"]},
            ).status_code
            == 403
        )
        assert (
            client.post(
                endpoint + "/approve",
                headers=reviewer,
                json={"digest": proposal["digest"]},
            ).status_code
            == 200
        )
        assert client.post(endpoint + "/execute", headers=alice).status_code == 200
        assert client.post(endpoint + "/execute", headers=alice).status_code == 409
        ticket = client.get("/api/tickets/IT-001", headers=alice).json()
        assert ticket["notes"] == [run["draft"]]
        assert ticket["version"] == 2
        evidence = client.get(endpoint, headers=reviewer).json()
        assert evidence["state"] == "executed"
        assert [event["event"] for event in evidence["events"]] == [
            "proposed",
            "approved",
            "executed",
        ]
