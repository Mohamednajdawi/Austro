"""Explicit live checks run separately from deterministic regression tests."""

# This script is intentionally not a pytest test function: run directly on demand.
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Provider, Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        settings = Settings(
            database_path=Path(folder) / "live.sqlite3",
            model_provider=Provider.OPENAI_COMPATIBLE
            if os.environ.get("ACG_TEST_COMPATIBLE") == "1"
            else Provider.OLLAMA,
        )
        store = Store(settings.database_path)
        store.initialize()
        store.seed_demo()
        store.add_knowledge_examples()
        headers = {"Authorization": f"Bearer {store.issue_session('alice', 3600)}"}
        with TestClient(create_app(settings)) as client:
            assert client.get("/readiness").status_code == 200
            for language, title, description in (
                (
                    "en",
                    "VPN error 809",
                    "My VPN connection fails with error 809 since this morning.",
                ),
                (
                    "de",
                    "VPN-Verbindung fehlgeschlagen",
                    "Meine VPN-Verbindung funktioniert seit heute nicht. "
                    "Fehlercode 809.",
                ),
                (
                    "en",
                    "Account access problem",
                    "I cannot access my account after the password expired.",
                ),
            ):
                ticket = client.post(
                    "/api/tickets",
                    headers=headers,
                    json={"title": title, "description": description},
                ).json()
                response = client.post(
                    "/api/runs",
                    headers=headers,
                    json={"ticket_id": ticket["id"], "language": language},
                )
                assert response.status_code == 201
                run = response.json()
                assert run["state"] == "awaiting_review", run
                assert run["model"].startswith(("ollama/", "openai-compatible/"))
                assert run["sources"], run
                assert len(run["draft"]) > 40
                print(f"LIVE PASS {language} / {title}: {run['draft']}")


if __name__ == "__main__":
    main()
