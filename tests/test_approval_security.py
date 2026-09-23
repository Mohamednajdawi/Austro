"""Reject stale approvals and serialize concurrent sandbox execution."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.approvals import Approvals, Conflict
from acg_agent_platform.services.store import AccessDenied, Store


def setup_proposal(tmp_path: Path) -> tuple[Store, Approvals, str]:
    settings = Settings(database_path=tmp_path / "sandbox.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    alice = {"Authorization": f"Bearer {store.issue_session('alice', 900)}"}
    with TestClient(create_app(settings)) as client:
        run = client.post(
            "/api/runs", headers=alice, json={"ticket_id": "IT-001"}
        ).json()
    approvals = Approvals(settings.database_path)
    proposal = approvals.propose(store.principal("alice"), run["id"])
    return store, approvals, proposal.id


def test_concurrent_execution_is_single_use(tmp_path: Path) -> None:
    store, approvals, pid = setup_proposal(tmp_path)
    alice, reviewer = store.principal("alice"), store.principal("reviewer")
    proposal = approvals.get(alice, pid)
    approvals.approve(reviewer, pid, proposal.digest)

    def attempt() -> str:
        try:
            return approvals.execute(alice, pid).state.value
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["conflict", "executed"]
    assert len(store.ticket(alice, "IT-001").notes) == 1


@pytest.mark.parametrize(
    "case", ["expired", "cancelled", "rejected", "revoked", "source", "tampered"]
)
def test_invalid_approval_never_writes(tmp_path: Path, case: str) -> None:
    store, approvals, pid = setup_proposal(tmp_path)
    alice, reviewer = store.principal("alice"), store.principal("reviewer")
    proposal = approvals.get(alice, pid)
    approvals.approve(reviewer, pid, proposal.digest)
    if case == "expired":
        approvals = Approvals(store.path, clock=lambda: proposal.action.expires_at + 1)
    elif case == "cancelled":
        approvals.close(alice, pid, reject=False)
    elif case == "rejected":
        approvals.close(reviewer, pid, reject=True)
    elif case == "revoked":
        store.set_principal_active("reviewer", False)
    elif case == "source":
        source = store.source(alice, "KB-VPN")
        store.put_source(
            source.model_copy(update={"content": "Silently changed content"})
        )
    else:
        with sqlite3.connect(store.path) as db:
            data = json.loads(
                db.execute(
                    "SELECT payload FROM proposals WHERE id=?", (pid,)
                ).fetchone()[0]
            )
            data["action"]["note"] = "Unapproved replacement"
            db.execute(
                "UPDATE proposals SET payload=? WHERE id=?", (json.dumps(data), pid)
            )
    with pytest.raises((Conflict, AccessDenied)):
        approvals.execute(alice, pid)
    assert store.ticket(alice, "IT-001").notes == ()


def test_wrong_digest_is_denied(tmp_path: Path) -> None:
    store, approvals, pid = setup_proposal(tmp_path)
    with pytest.raises(Conflict):
        approvals.approve(store.principal("reviewer"), pid, "0" * 64)
    assert not store.ticket(store.principal("alice"), "IT-001").notes
