"""Atomic local approval and execution with independent authorization checks."""

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from acg_agent_platform.models.approval import (
    Action,
    Proposal,
    ProposalState,
    ReviewEvent,
)
from acg_agent_platform.models.platform import AgentRevision
from acg_agent_platform.models.records import (
    Classification,
    Principal,
    Role,
    Source,
    Ticket,
)
from acg_agent_platform.models.workflow import Run, RunState
from acg_agent_platform.services.store import AccessDenied


class Conflict(Exception):
    """Action state or dependencies no longer permit the operation."""


class Forbidden(Exception):
    """Authenticated actor lacks required action authority."""


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def action_digest(action: Action) -> str:
    return fingerprint(
        json.dumps(
            action.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


class Approvals:
    def __init__(
        self, path: Path, lifetime: int = 900, clock: Callable[[], float] = time.time
    ) -> None:
        self.path = path
        self.lifetime = lifetime
        self.clock = clock

    def propose(self, actor: Principal, run_id: str) -> Proposal:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            row = db.execute(
                "SELECT payload FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise AccessDenied
            run = Run.model_validate_json(row[0])
            if run.owner_id != actor.id or run.workspace != actor.workspace:
                raise AccessDenied
            if (
                run.state != RunState.AWAITING_REVIEW
                or not run.sources
                or not run.draft
            ):
                raise Conflict("Only a source-backed draft can become an action")
            if db.execute(
                "SELECT id FROM proposals WHERE run_id=?", (run_id,)
            ).fetchone():
                raise Conflict("A proposal already exists for this run")
            ticket = self._ticket(db, run.ticket_id)
            if (
                ticket.version != run.ticket_version
                or ticket.workspace != actor.workspace
            ):
                raise Conflict("Ticket changed; generate a fresh draft")
            action = Action(
                run_id=run.id,
                requester_id=actor.id,
                workspace=actor.workspace,
                ticket_id=ticket.id,
                ticket_fingerprint=fingerprint(ticket.model_dump_json()),
                ticket_version=ticket.version,
                note=run.draft,
                sources=run.sources,
                screening=run.screening,
                expires_at=self.clock() + self.lifetime,
            )
            proposal = Proposal(
                id=str(uuid4()),
                action=action,
                digest=action_digest(action),
                events=(self._event("proposed", actor.id),),
            )
            self._validate(db, proposal, actor, check_target=True)
            db.execute(
                "INSERT INTO proposals VALUES (?, ?, ?)",
                (proposal.id, run.id, proposal.model_dump_json()),
            )
            return proposal

    def get(self, actor: Principal, proposal_id: str) -> Proposal:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            proposal = self._load(db, proposal_id)
            self._visible(proposal, actor)
            self._sources(db, proposal.action, actor)
            return proposal

    def list(self, actor: Principal) -> tuple[Proposal, ...]:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            rows = db.execute(
                "SELECT payload FROM proposals ORDER BY rowid DESC LIMIT 200"
            ).fetchall()
            visible = []
            for row in rows:
                proposal = Proposal.model_validate_json(row[0])
                try:
                    self._visible(proposal, actor)
                    self._sources(db, proposal.action, actor)
                except (AccessDenied, Conflict):
                    continue
                visible.append(proposal)
            return tuple(visible)

    def approve(self, actor: Principal, proposal_id: str, digest: str) -> Proposal:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            proposal = self._load(db, proposal_id)
            self._visible(proposal, actor)
            if actor.role != Role.REVIEWER or actor.id == proposal.action.requester_id:
                raise Forbidden("A different authorized reviewer is required")
            if proposal.state != ProposalState.PENDING or digest != proposal.digest:
                raise Conflict("Proposal is no longer pending or digest does not match")
            self._validate(db, proposal, actor, check_target=True)
            proposal = proposal.model_copy(
                update={
                    "state": ProposalState.APPROVED,
                    "approver_id": actor.id,
                    "events": (*proposal.events, self._event("approved", actor.id)),
                }
            )
            self._save(db, proposal)
            return proposal

    def execute(self, actor: Principal, proposal_id: str) -> Proposal:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            proposal = self._load(db, proposal_id)
            self._visible(proposal, actor)
            if proposal.state != ProposalState.APPROVED or not proposal.approver_id:
                raise Conflict("A valid unused approval is required")
            self._validate(db, proposal, actor, check_target=True)
            approver = self._principal(db, proposal.approver_id)
            if (
                approver.role != Role.REVIEWER
                or approver.id == proposal.action.requester_id
            ):
                raise Forbidden("Approval authority is no longer valid")
            self._validate(db, proposal, approver, check_target=True)
            ticket = self._ticket(db, proposal.action.ticket_id)
            updated = ticket.model_copy(
                update={
                    "notes": (*ticket.notes, proposal.action.note),
                    "version": ticket.version + 1,
                }
            )
            db.execute(
                "UPDATE tickets SET payload=? WHERE id=?",
                (updated.model_dump_json(), ticket.id),
            )
            proposal = proposal.model_copy(
                update={
                    "state": ProposalState.EXECUTED,
                    "events": (*proposal.events, self._event("executed", actor.id)),
                }
            )
            self._save(db, proposal)
            return proposal

    def close(self, actor: Principal, proposal_id: str, reject: bool) -> Proposal:
        with self._transaction() as db:
            actor = self._principal(db, actor.id)
            proposal = self._load(db, proposal_id)
            self._visible(proposal, actor)
            if reject and actor.role != Role.REVIEWER:
                raise Forbidden("Reviewer required")
            if not reject and actor.id != proposal.action.requester_id:
                raise Forbidden("Only requester may cancel")
            if proposal.state not in (ProposalState.PENDING, ProposalState.APPROVED):
                raise Conflict("Proposal already closed")
            self._sources(db, proposal.action, actor)
            state = ProposalState.REJECTED if reject else ProposalState.CANCELLED
            proposal = proposal.model_copy(
                update={
                    "state": state,
                    "events": (*proposal.events, self._event(state.value, actor.id)),
                }
            )
            self._save(db, proposal)
            return proposal

    def _validate(
        self,
        db: sqlite3.Connection,
        proposal: Proposal,
        actor: Principal,
        *,
        check_target: bool,
    ) -> None:
        action = proposal.action
        if proposal.digest != action_digest(action):
            raise Conflict("Action integrity check failed")
        if action.expires_at <= self.clock():
            raise Conflict("Approval window expired; create a new run")
        if action.policy_version != "internal-only-v1":
            raise Conflict("Policy changed")
        row = db.execute(
            "SELECT payload FROM runs WHERE id=?", (action.run_id,)
        ).fetchone()
        if row is None:
            raise Conflict("Originating run unavailable")
        run = Run.model_validate_json(row[0])
        configured = db.execute(
            "SELECT payload FROM agent_profiles WHERE workspace=? AND template=? "
            "ORDER BY version DESC LIMIT 1",
            (action.workspace, run.use_case),
        ).fetchone()
        if configured:
            profile = AgentRevision.model_validate_json(configured[0])
            if not profile.enabled or profile.version != run.agent_version:
                raise Conflict("Agent configuration changed; create a new run")
        requester = self._principal(db, action.requester_id)
        self._sources(db, action, requester)
        self._sources(db, action, actor)
        if check_target:
            ticket = self._ticket(db, action.ticket_id)
            if (
                ticket.workspace != action.workspace
                or ticket.classification != Classification.INTERNAL
                or fingerprint(ticket.model_dump_json()) != action.ticket_fingerprint
            ):
                raise Conflict("Target changed or destination policy denied")

    def _sources(
        self, db: sqlite3.Connection, action: Action, actor: Principal
    ) -> None:
        if actor.workspace != action.workspace:
            raise AccessDenied
        ticket = self._ticket(db, action.ticket_id)
        if (
            ticket.workspace != actor.workspace
            or ticket.classification != Classification.INTERNAL
        ):
            raise AccessDenied
        for citation in action.sources:
            row = db.execute(
                "SELECT payload FROM sources WHERE id=?", (citation.id,)
            ).fetchone()
            if row is None:
                raise AccessDenied
            source = Source.model_validate_json(row[0])
            if (
                not source.active
                or source.workspace != actor.workspace
                or actor.role not in source.allowed_roles
            ):
                raise AccessDenied
            # Workspace-visible notes require inputs readable by every workspace role.
            if (
                source.classification != Classification.INTERNAL
                or not set(Role).issubset(source.allowed_roles)
                or source.version != citation.version
                or not citation.fingerprint
                or fingerprint(source.model_dump_json()) != citation.fingerprint
            ):
                raise Conflict("Source changed or destination audience is too broad")

    def _visible(self, proposal: Proposal, actor: Principal) -> None:
        if actor.workspace != proposal.action.workspace or (
            actor.id != proposal.action.requester_id and actor.role != Role.REVIEWER
        ):
            raise AccessDenied

    def _principal(self, db: sqlite3.Connection, principal_id: str) -> Principal:
        row = db.execute(
            "SELECT payload FROM principals WHERE id=?", (principal_id,)
        ).fetchone()
        if row is None:
            raise AccessDenied
        principal = Principal.model_validate_json(row[0])
        if not principal.active:
            raise AccessDenied
        return principal

    def _ticket(self, db: sqlite3.Connection, ticket_id: str) -> Ticket:
        row = db.execute(
            "SELECT payload FROM tickets WHERE id=?", (ticket_id,)
        ).fetchone()
        if row is None:
            raise AccessDenied
        return Ticket.model_validate_json(row[0])

    def _load(self, db: sqlite3.Connection, proposal_id: str) -> Proposal:
        row = db.execute(
            "SELECT payload FROM proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise AccessDenied
        return Proposal.model_validate_json(row[0])

    def _save(self, db: sqlite3.Connection, proposal: Proposal) -> None:
        db.execute(
            "UPDATE proposals SET payload=? WHERE id=?",
            (proposal.model_dump_json(), proposal.id),
        )

    def _event(self, event: str, actor: str) -> ReviewEvent:
        return ReviewEvent(event=event, actor=actor, timestamp=self.clock())

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()
