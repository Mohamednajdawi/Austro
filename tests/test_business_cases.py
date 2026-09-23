"""Business cases must calculate facts, preserve authorization and require review."""

from pathlib import Path

from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def test_invoice_discrepancy_and_infrastructure_dependencies(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "cases.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    store.seed_business_examples()
    finance = {"Authorization": f"Bearer {store.issue_session('bob', 900)}"}
    it = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    with TestClient(create_app(settings)) as client:
        invoice = client.post(
            "/api/cases/invoice",
            headers=finance,
            json={
                "invoice_id": "INV-2026-1",
                "supplier_id": "SUP-01",
                "order_source_id": "PO-100",
                "supplier_source_id": "SUP-01",
                "contract_source_id": "CON-100",
                "net": "10333.33",
                "vat": "2066.67",
                "total": "12400.00",
                "currency": "EUR",
                "bank_account": "AT611904300234573201",
                "language": "en",
            },
        )
        assert invoice.status_code == 201, invoice.text
        run = invoice.json()
        assert run["use_case"] == "invoice"
        assert "2400.00" in run["draft"]
        assert "No payment" in run["draft"]
        assert (
            client.post(
                "/api/runs/" + run["id"] + "/proposal", headers=finance
            ).status_code
            == 201
        )
        assert client.get("/api/runs/" + run["id"], headers=it).status_code == 404
        infrastructure = client.post(
            "/api/cases/infrastructure",
            headers=it,
            json={
                "asset_source_id": "ASSET-EDGE",
                "request": "Plan a network maintenance window",
                "language": "en",
            },
        )
        assert infrastructure.status_code == 201, infrastructure.text
        assert "ASSET-APP" in infrastructure.json()["draft"]
        assert "No production change" in infrastructure.json()["draft"]
