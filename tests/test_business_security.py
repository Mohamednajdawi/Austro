"""Business reports remain scoped, deterministic and approval-controlled."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store

INVOICE = {
    "invoice_id": "INV-1",
    "supplier_id": "SUP-01",
    "order_source_id": "PO-100",
    "supplier_source_id": "SUP-01",
    "contract_source_id": "CON-100",
    "net": "10333.33",
    "vat": "2066.67",
    "total": "12400.00",
    "currency": "EUR",
    "bank_account": "AT611904300234573201",
}


@pytest.fixture
def setup(tmp_path: Path):
    settings = Settings(database_path=tmp_path / "business.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    store.seed_business_examples()
    headers = {
        name: {"Authorization": f"Bearer {store.issue_session(name, 900)}"}
        for name in ("alice", "reviewer", "bob", "finance-reviewer")
    }
    with TestClient(create_app(settings)) as client:
        yield client, store, headers


def test_invoice_requires_finance_reviewer_and_executes_only_note(setup) -> None:
    client, store, headers = setup
    run = client.post("/api/cases/invoice", json=INVOICE, headers=headers["bob"]).json()
    proposal = client.post(
        f"/api/runs/{run['id']}/proposal", headers=headers["bob"]
    ).json()
    endpoint = f"/api/proposals/{proposal['id']}"
    assert (
        client.post(
            endpoint + "/approve",
            headers=headers["reviewer"],
            json={"digest": proposal["digest"]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            endpoint + "/approve",
            headers=headers["finance-reviewer"],
            json={"digest": proposal["digest"]},
        ).status_code
        == 200
    )
    assert client.post(endpoint + "/execute", headers=headers["bob"]).status_code == 200
    assert store.ticket(store.principal("bob"), run["ticket_id"]).notes == (
        run["draft"],
    )
    assert client.post("/api/payments", headers=headers["bob"]).status_code == 404


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"vat": "2000.00"}, "VAT/arithmetic mismatch"),
        ({"currency": "USD"}, "Currency mismatch"),
        ({"bank_account": "CH9300762011623852957"}, "Bank details differ"),
        ({"supplier_id": "OTHER"}, "Supplier mismatch"),
    ],
)
def test_invoice_discrepancies_are_deterministic(setup, changes, expected) -> None:
    client, _, headers = setup
    run = client.post(
        "/api/cases/invoice", json={**INVOICE, **changes}, headers=headers["bob"]
    ).json()
    assert expected in run["draft"]
    assert run["model"] == "deterministic/business-tools-v1"
    assert run["model_calls"] == len(run["screening"]["findings"])


def test_invalid_money_and_cross_workspace_sources_rejected(setup) -> None:
    client, _, headers = setup
    for bad in (12400.0, "NaN", "-1.00", "12,400.00", "1.234"):
        assert (
            client.post(
                "/api/cases/invoice",
                headers=headers["bob"],
                json={**INVOICE, "total": bad},
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/api/cases/invoice", headers=headers["alice"], json=INVOICE
        ).status_code
        == 404
    )


def test_disabled_agent_invalidates_existing_approval(setup) -> None:
    client, _, headers = setup
    run = client.post("/api/cases/invoice", json=INVOICE, headers=headers["bob"]).json()
    proposal = client.post(
        f"/api/runs/{run['id']}/proposal", headers=headers["bob"]
    ).json()
    endpoint = f"/api/proposals/{proposal['id']}"
    client.post(
        endpoint + "/approve",
        headers=headers["finance-reviewer"],
        json={"digest": proposal["digest"]},
    )
    client.put(
        "/api/agents",
        headers=headers["finance-reviewer"],
        json={"template": "invoice", "name": "Disabled invoice", "enabled": False},
    )
    assert client.post(endpoint + "/execute", headers=headers["bob"]).status_code == 409


def test_stale_and_incomplete_infrastructure_is_explicit(setup) -> None:
    client, store, headers = setup
    source = store.source(store.principal("alice"), "ASSET-APP")
    content = json.loads(source.content)
    content.update(
        updated_at="2020-01-01",
        depends_on=["ASSET-EDGE", "UNKNOWN-ASSET"],
        safety_critical=True,
    )
    store.put_source(source.model_copy(update={"content": json.dumps(content)}))
    run = client.post(
        "/api/cases/infrastructure",
        headers=headers["alice"],
        json={"asset_source_id": "ASSET-EDGE", "request": "Plan maintenance"},
    ).json()
    assert "Stale" in run["draft"]
    assert "Incomplete" in run["draft"]
    assert "Safety-critical" in run["draft"]
    assert "UNKNOWN-ASSET" not in run["draft"]
