"""Bounded configuration and ingestion contracts with no arbitrary executable code."""

from typing import Literal

from pydantic import Field

from acg_agent_platform.models.business import Identifier
from acg_agent_platform.models.records import Classification, Record, Role

Template = Literal["it_support", "invoice", "infrastructure"]


class AgentProfile(Record):
    template: Template
    name: str = Field(min_length=3, max_length=80)
    enabled: bool = Field(default=True, strict=True)
    max_sources: int = Field(default=5, ge=1, le=5, strict=True)


class AgentRevision(AgentProfile):
    version: int = 1
    updated_by: str


class SourceInput(Record):
    title: str = Field(strict=True, min_length=3, max_length=160)
    content: str = Field(strict=True, min_length=8, max_length=20000)
    topic: Identifier
    classification: Classification = Classification.UNKNOWN
    allowed_roles: tuple[Role, ...] = (Role.REVIEWER,)
    source_type: Literal["document", "incident", "log", "email", "wiki", "business"] = (
        "document"
    )


class ExtractDocument(Record):
    filename: str = Field(strict=True, min_length=1, max_length=180)
    data_base64: str = Field(strict=True, min_length=4, max_length=1400000)


class PolicyProbe(Record):
    text: str = Field(strict=True, max_length=20000)
    classification: Classification = Classification.UNKNOWN
    destination: Literal["local", "external"] = "local"
