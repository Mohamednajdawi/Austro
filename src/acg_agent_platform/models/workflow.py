"""Typed model and workflow contracts with no action authority."""

from enum import StrEnum

from pydantic import Field

from acg_agent_platform.models.records import Classification, Record


class Language(StrEnum):
    EN = "en"
    DE = "de"


class Stage(StrEnum):
    CLASSIFY = "classify"
    DRAFT = "draft"


class RunState(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    BLOCKED = "blocked"
    FAILED = "failed"


class StartRun(Record):
    ticket_id: str = Field(
        strict=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    language: Language = Language.EN


class Citation(Record):
    id: str
    version: int
    fingerprint: str = ""


class Envelope(Record):
    stage: Stage
    language: Language
    text: str
    classification: Classification


class Category(StrEnum):
    VPN = "vpn"
    ACCOUNT = "account"
    NETWORK = "network"
    UNKNOWN = "unknown"


class ClassificationResult(Record):
    category: Category


class DraftResult(Record):
    draft: str = Field(strict=True, min_length=1, max_length=8000)


class Evidence(Record):
    stage: str
    outcome: str
    timestamp: float


class Run(Record):
    framework: str = "langgraph"
    use_case: str = "it_support"
    agent_version: int = 1
    id: str
    owner_id: str
    workspace: str
    ticket_id: str
    ticket_version: int
    language: Language
    state: RunState
    draft: str
    sources: tuple[Citation, ...]
    model: str
    model_calls: int
    workflow_version: str = "it-draft-v1"
    policy_version: str = "internal-only-v1"
    prompt_version: str = "draft-v1"
    evidence: tuple[Evidence, ...]
