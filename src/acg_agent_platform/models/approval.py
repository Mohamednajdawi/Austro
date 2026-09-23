"""Immutable action proposals and explicit review states."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from acg_agent_platform.models.records import Record
from acg_agent_platform.models.workflow import Citation


class ProposalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXECUTED = "executed"


class Action(Record):
    kind: Literal["append_sandbox_note"] = "append_sandbox_note"
    run_id: str
    requester_id: str
    workspace: str
    ticket_id: str
    ticket_fingerprint: str
    ticket_version: int
    note: str
    sources: tuple[Citation, ...]
    policy_version: str = "internal-only-v1"
    expires_at: float


class ReviewEvent(Record):
    event: str
    actor: str
    timestamp: float


class Proposal(Record):
    id: str
    action: Action
    digest: str
    state: ProposalState = ProposalState.PENDING
    approver_id: str | None = None
    events: tuple[ReviewEvent, ...]


class ApprovalRequest(Record):
    digest: str = Field(strict=True, pattern=r"^[a-f0-9]{64}$")


class NewTicket(Record):
    title: str = Field(strict=True, min_length=3, max_length=160)
    description: str = Field(strict=True, min_length=5, max_length=8000)
