"""Configuration, ingestion and policy remain bounded by server authorization."""

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_sources_require_reviewer_and_profile_controls_execution(
    tmp_path: Path,
) -> None:
    settings = Settings(database_path=tmp_path / "platform.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    alice = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    reviewer = {"Authorization": f"Bearer {store.issue_session('reviewer', 900)}"}
    with TestClient(create_app(settings)) as client:
        body = {
            "title": "Approved VPN guidance",
            "content": "Collect error code; contact IT.",
            "topic": "vpn",
            "classification": "internal",
            "allowed_roles": ["support", "reviewer"],
        }
        assert client.post("/api/sources", headers=alice, json=body).status_code == 403
        source = client.post("/api/sources", headers=reviewer, json=body).json()
        assert (
            client.get("/api/sources/" + source["id"], headers=alice).status_code == 200
        )
        assert (
            client.delete("/api/sources/" + source["id"], headers=reviewer).status_code
            == 200
        )
        assert (
            client.get("/api/sources/" + source["id"], headers=alice).status_code == 404
        )
        profile = {
            "template": "it_support",
            "name": "Support restricted",
            "enabled": False,
            "max_sources": 2,
        }
        assert client.put("/api/agents", headers=alice, json=profile).status_code == 403
        assert (
            client.put("/api/agents", headers=reviewer, json=profile).status_code == 200
        )
        assert (
            client.post(
                "/api/runs", headers=alice, json={"ticket_id": "IT-001"}
            ).status_code
            == 403
        )
        assert (
            client.get("/api/platform", headers=alice).json()["framework"]
            == "LangGraph"
        )


def test_extraction_is_not_publication_and_external_policy_is_denied(
    tmp_path: Path,
) -> None:
    settings = Settings(database_path=tmp_path / "extract.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    headers = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    with TestClient(create_app(settings)) as client:
        before = client.get("/api/sources", headers=headers).json()
        response = client.post(
            "/api/documents/extract",
            headers=headers,
            json={
                "filename": "guide.txt",
                "data_base64": base64.b64encode(
                    b"VPN: collect the error code."
                ).decode(),
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["published"] is False
        assert client.get("/api/sources", headers=headers).json() == before
        response = client.post(
            "/api/policy/inspect",
            headers=headers,
            json={
                "text": "person@example.com",
                "classification": "internal",
                "destination": "external",
            },
        )
        assert response.json()["allowed"] is False
        assert "email" in response.json()["indicators"]
