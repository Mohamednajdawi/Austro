"""Search and ingestion cannot silently widen source permissions."""

from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_search_filters_workspace_and_sensitive_publication(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "search.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    alice = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    reviewer = {"Authorization": f"Bearer {store.issue_session('reviewer', 900)}"}
    with TestClient(create_app(settings)) as client:
        result = client.get("/api/search?q=VPN", headers=alice)
        ids = [source["id"] for source in result.json()]
        assert "KB-VPN" in ids
        assert "KB-FIN" not in ids and "KB-RESTRICTED" not in ids
        result = client.post(
            "/api/sources",
            headers=reviewer,
            json={
                "title": "Sensitive imported email",
                "topic": "vpn",
                "content": "Contact person@example.com for VPN support.",
                "classification": "internal",
                "allowed_roles": ["support", "reviewer"],
            },
        )
        assert result.json()["classification"] == "restricted"
