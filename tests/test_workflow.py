"""Verify useful synthetic drafts without granting models action authority."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.models.records import Classification, Role, Source
from acg_agent_platform.models.workflow import Envelope, Stage
from acg_agent_platform.services.gateway import BaseModelAdapter, BasePolicy, FakeModel
from acg_agent_platform.services.store import Store


def test_draft_uses_only_authorized_sources_and_stops_for_review(
    tmp_path: Path,
) -> None:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", lifetime=900)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(settings)) as client:
        before = client.get("/api/tickets/IT-001", headers=headers).json()
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001", "language": "de"}
        )
        assert response.status_code == 201
        run = response.json()
        assert run["state"] == "awaiting_review"
        assert run["model"] == "fake/deterministic-v1"
        assert [source["id"] for source in run["sources"]] == ["KB-VPN"]
        assert "KB-RESTRICTED" not in response.text
        assert "KB-FIN" not in response.text
        assert run["model_calls"] == 4
        assert "Prüfung" in run["draft"]
        assert client.get("/api/tickets/IT-001", headers=headers).json() == before
        saved = client.get(f"/api/runs/{run['id']}", headers=headers)
        assert saved.json() == run


class SpyModel(BaseModelAdapter):
    name = "fake/spy-v1"

    def __init__(self) -> None:
        self.received: list[Envelope] = []

    def infer(self, envelope: Envelope) -> str:
        self.received.append(envelope)
        return FakeModel().infer(envelope)


def provision(tmp_path: Path) -> tuple[Settings, Store, dict[str, str]]:
    settings = Settings(database_path=tmp_path / "demo.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    token = store.issue_session("alice", lifetime=900)
    return settings, store, {"Authorization": f"Bearer {token}"}


def test_unauthorized_content_never_reaches_model(tmp_path: Path) -> None:
    settings, _, headers = provision(tmp_path)
    model = SpyModel()
    with TestClient(create_app(settings, model=model)) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        )
    assert response.status_code == 201
    assert [envelope.stage for envelope in model.received] == [
        Stage.CLASSIFY,
        Stage.DRAFT,
        Stage.JUDGE,
        Stage.JUDGE,
    ]
    assert "KB-VPN" in model.received[1].text
    for envelope in model.received:
        assert "Restricted synthetic" not in envelope.text
        assert "Finance-only" not in envelope.text


def test_accessible_but_restricted_context_blocks_second_model_call(
    tmp_path: Path,
) -> None:
    settings, store, _ = provision(tmp_path)
    token = store.issue_session("reviewer", lifetime=900)
    model = SpyModel()
    with TestClient(create_app(settings, model=model)) as client:
        response = client.post(
            "/api/runs",
            json={"ticket_id": "IT-001"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.json()["state"] == "blocked"
    assert response.json()["draft"] == ""
    assert len(model.received) == 1


def test_oversize_first_payload_causes_zero_model_calls(tmp_path: Path) -> None:
    settings, _, headers = provision(tmp_path)
    settings = Settings(database_path=settings.database_path, max_context_chars=1)
    model = SpyModel()
    with TestClient(create_app(settings, model=model)) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        )
    assert response.json()["state"] == "blocked"
    assert not model.received


@pytest.mark.parametrize("change", ["revoked", "deleted", "version"])
def test_saved_draft_rechecks_source_access(tmp_path: Path, change: str) -> None:
    settings, store, headers = provision(tmp_path)
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
        source = store.source(store.principal("alice"), "KB-VPN")
        update: dict[str, object] = {
            "revoked": {"allowed_roles": (Role.REVIEWER,)},
            "deleted": {"active": False},
            "version": {"version": 2},
        }[change]
        store.put_source(source.model_copy(update=update))
        assert client.get(f"/api/runs/{run['id']}", headers=headers).status_code == 404
    with TestClient(create_app(settings)) as restarted:
        assert (
            restarted.get(f"/api/runs/{run['id']}", headers=headers).status_code == 404
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"approved": True},
        {"role": "reviewer"},
        {"workspace": "finance"},
        {"tool": "shell"},
        {"ticket_id": 123},
        {"language": "xx"},
    ],
)
def test_action_or_identity_fields_cannot_be_smuggled(
    tmp_path: Path, extra: dict[str, object]
) -> None:
    settings, _, headers = provision(tmp_path)
    model = SpyModel()
    with TestClient(create_app(settings, model=model)) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001", **extra}
        )
    assert response.status_code == 422
    assert not model.received


class InvalidModel(BaseModelAdapter):
    name = "fake/invalid-v1"

    def infer(self, envelope: Envelope) -> str:
        if envelope.stage == Stage.CLASSIFY:
            return '{"category":"vpn"}'
        return '{"draft":"dangerous", "execute":"shell"}'


def test_model_cannot_request_execution_through_extra_fields(tmp_path: Path) -> None:
    settings, _, headers = provision(tmp_path)
    with TestClient(create_app(settings, model=InvalidModel())) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
        assert run["state"] == "failed"
        assert run["draft"] == ""
        assert (
            client.post(f"/api/runs/{run['id']}/execute", headers=headers).status_code
            == 404
        )


class UnavailablePolicy(BasePolicy):
    def inspect(self, envelope: Envelope) -> None:
        raise TimeoutError("synthetic-sensitive-error")


def test_policy_outage_fails_closed_without_leaking_error(tmp_path: Path) -> None:
    settings, _, headers = provision(tmp_path)
    model = SpyModel()
    with TestClient(
        create_app(settings, model=model, policy=UnavailablePolicy())
    ) as client:
        response = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        )
    assert response.json()["state"] == "failed"
    assert not model.received
    assert "synthetic-sensitive-error" not in response.text


def test_no_evidence_yields_uncertainty_not_invented_answer(tmp_path: Path) -> None:
    settings, store, headers = provision(tmp_path)
    source = store.source(store.principal("alice"), "KB-VPN")
    store.put_source(source.model_copy(update={"active": False}))
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
    assert "Insufficient" in run["draft"]
    assert run["sources"] == []
    assert run["model_calls"] == 2


def test_unknown_classification_is_denied_before_drafting(tmp_path: Path) -> None:
    settings, store, headers = provision(tmp_path)
    store.put_source(
        Source(
            id="KB-UNKNOWN",
            workspace="it",
            title="Unknown",
            content="Unclassified content",
            topic="vpn",
            allowed_roles=(Role.SUPPORT,),
            classification=Classification.UNKNOWN,
        )
    )
    model = SpyModel()
    with TestClient(create_app(settings, model=model)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
    assert run["state"] == "blocked"
    assert len(model.received) == 1


def test_run_evidence_is_owner_scoped(tmp_path: Path) -> None:
    settings, store, headers = provision(tmp_path)
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=headers, json={"ticket_id": "IT-001"}
        ).json()
        for principal in ("bob", "reviewer"):
            token = store.issue_session(principal, lifetime=900)
            assert (
                client.get(
                    f"/api/runs/{run['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                ).status_code
                == 404
            )
