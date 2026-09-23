"""Reviewer-owned configuration and authorized source administration."""

import sqlite3
from uuid import uuid4

from acg_agent_platform.models.approval import Proposal
from acg_agent_platform.models.platform import AgentProfile, AgentRevision, SourceInput
from acg_agent_platform.models.records import Classification, Principal, Role, Source
from acg_agent_platform.models.workflow import Run
from acg_agent_platform.services.approvals import Forbidden
from acg_agent_platform.services.content_policy import indicators
from acg_agent_platform.services.store import Store

TOOL_CATALOG = (
    {
        "id": "knowledge_search",
        "mode": "read",
        "scope": "authorized local source records",
    },
    {"id": "ticket_read", "mode": "read", "scope": "authorized sandbox tickets"},
    {
        "id": "invoice_compare",
        "mode": "read",
        "scope": "typed order, supplier and contract records",
    },
    {
        "id": "asset_dependencies",
        "mode": "read",
        "scope": "authorized local asset records",
    },
    {
        "id": "document_extract",
        "mode": "read",
        "scope": "bounded local PDF/text/EML uploads",
    },
    {
        "id": "append_sandbox_note",
        "mode": "approved_write",
        "scope": "exact approved review note",
    },
)


class Platform:
    def __init__(self, store: Store) -> None:
        self.store = store

    def profiles(self, actor: Principal) -> tuple[AgentRevision, ...]:
        actor = self.store.principal(actor.id)
        with sqlite3.connect(self.store.path) as db:
            rows = db.execute(
                "SELECT payload FROM agent_profiles WHERE workspace=? ORDER BY rowid",
                (actor.workspace,),
            ).fetchall()
        latest: dict[str, AgentRevision] = {
            item.template: item
            for row in rows
            for item in [AgentRevision.model_validate_json(row[0])]
        }
        return tuple(
            latest.get(
                template,
                AgentRevision(template=template, name=name, updated_by="system"),
            )
            for template, name in (
                ("it_support", "IT support"),
                ("invoice", "Invoice review"),
                ("infrastructure", "Infrastructure planning"),
            )
        )

    def monitoring(self, actor: Principal) -> dict[str, object]:
        actor = self.store.principal(actor.id)
        with sqlite3.connect(self.store.path) as db:
            rows = db.execute("SELECT payload FROM runs ORDER BY rowid DESC").fetchall()
            proposal_rows = db.execute("SELECT payload FROM proposals").fetchall()
        proposals = {
            p.action.run_id: p.state.value
            for row in proposal_rows
            for p in [Proposal.model_validate_json(row[0])]
        }
        runs = [
            r
            for row in rows
            for r in [Run.model_validate_json(row[0])]
            if r.owner_id == actor.id and r.workspace == actor.workspace
        ][:100]
        return {
            "scope": "own latest 100 runs",
            "model_calls": sum(r.model_calls for r in runs),
            "runs": [
                {
                    "id": r.id,
                    "use_case": r.use_case,
                    "model": r.model,
                    "state": proposals.get(r.id, r.state.value),
                    "agent_version": r.agent_version,
                    "processing_steps": len(r.evidence),
                }
                for r in runs
            ],
            "cost": "Model calls are measured; monetary costs require pricing data.",
        }

    def configure(self, actor: Principal, profile: AgentProfile) -> AgentRevision:
        actor = self._reviewer(actor)
        with sqlite3.connect(self.store.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT MAX(version) FROM agent_profiles "
                "WHERE workspace=? AND template=?",
                (actor.workspace, profile.template),
            ).fetchone()
            revision = AgentRevision(
                **profile.model_dump(),
                version=int(row[0] or 1) + 1,
                updated_by=actor.id,
            )
            db.execute(
                "INSERT INTO agent_profiles VALUES (?, ?, ?, ?)",
                (
                    actor.workspace,
                    profile.template,
                    revision.version,
                    revision.model_dump_json(),
                ),
            )
        return revision

    def profile(self, actor: Principal, template: str) -> AgentRevision:
        profile = next(
            item for item in self.profiles(actor) if item.template == template
        )
        if not profile.enabled:
            raise Forbidden("Agent template disabled by workspace reviewer")
        return profile

    def add_source(self, actor: Principal, body: SourceInput) -> Source:
        actor = self._reviewer(actor)
        classification = body.classification
        if indicators(body.content):
            classification = Classification.RESTRICTED
        source = Source(
            id="DOC-" + uuid4().hex[:16],
            workspace=actor.workspace,
            title=body.title,
            content=body.content,
            topic=body.topic,
            allowed_roles=body.allowed_roles,
            source_type=body.source_type,
            classification=classification,
        )
        self.store.put_source(source)
        return source

    def retire_source(self, actor: Principal, source_id: str) -> Source:
        actor = self._reviewer(actor)
        source = self.store.source(actor, source_id)
        source = source.model_copy(
            update={"active": False, "version": source.version + 1}
        )
        self.store.put_source(source)
        return source

    def _reviewer(self, actor: Principal) -> Principal:
        actor = self.store.principal(actor.id)
        if actor.role != Role.REVIEWER:
            raise Forbidden("Workspace reviewer required")
        return actor
