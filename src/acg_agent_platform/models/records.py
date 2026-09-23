"""Immutable synthetic domain records."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    SUPPORT = "support"
    REVIEWER = "reviewer"


class Classification(StrEnum):
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Principal(Record):
    id: str
    workspace: str
    role: Role
    active: bool = True


class Ticket(Record):
    id: str
    workspace: str
    title: str
    description: str
    classification: Classification = Classification.INTERNAL
    version: int = Field(default=1, ge=1)
    notes: tuple[str, ...] = ()


class Source(Record):
    source_type: Literal["document", "incident", "log", "email", "wiki", "business"] = (
        "document"
    )
    id: str
    workspace: str
    title: str
    content: str
    topic: str
    allowed_roles: tuple[Role, ...]
    classification: Classification = Classification.INTERNAL
    version: int = Field(default=1, ge=1)
    active: bool = True
