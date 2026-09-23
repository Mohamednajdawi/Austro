"""A failed final checkpoint must never cause duplicate business effects."""

from pathlib import Path

import pytest

from acg_agent_platform.config import Settings
from acg_agent_platform.models.workflow import StartRun
from acg_agent_platform.services.approvals import Approvals, Conflict
from acg_agent_platform.services.gateway import FakeModel, InternalOnlyPolicy
from acg_agent_platform.services.store import Store
from acg_agent_platform.services.workflow import Workflow


def test_reconcile_committed_action_after_node_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(database_path=tmp_path / "recover.sqlite3")
    store = Store(settings.database_path)
    store.initialize()
    store.seed_demo()
    actor = store.principal("alice")
    workflow = Workflow(store, settings, FakeModel(), InternalOnlyPolicy(20000))
    run = workflow.start(actor, StartRun(ticket_id="IT-001"))
    approvals = Approvals(store.path)
    proposal = approvals.propose(actor, run.id)
    with pytest.raises(Conflict):
        workflow.reconcile(actor, proposal.id)
    approvals.approve(store.principal("reviewer"), proposal.id, proposal.digest)
    original = workflow.approvals.execute

    def fail_after_commit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Simulated crash after independent action commit")

    monkeypatch.setattr(workflow.approvals, "execute", fail_after_commit)
    with pytest.raises(RuntimeError):
        workflow.execute(actor, proposal.id)
    assert len(store.ticket(actor, "IT-001").notes) == 1
    restarted = Workflow(store, settings, FakeModel(), InternalOnlyPolicy(20000))
    assert restarted.reconcile(actor, proposal.id)["reconciled"] is True
    assert restarted.inspect(actor, run.id)["completed"] is True
    assert len(store.ticket(actor, "IT-001").notes) == 1
