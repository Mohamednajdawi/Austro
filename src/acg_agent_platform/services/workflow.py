"""Durable LangGraph agents with policy gates and independently authorized actions."""

import hashlib
import json
import time
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from importlib.resources import files
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context
from pydantic import ValidationError

from acg_agent_platform.config import Settings
from acg_agent_platform.models.approval import Proposal, ProposalState
from acg_agent_platform.models.business import InfrastructureRequest, InvoiceRequest
from acg_agent_platform.models.records import Classification, Principal
from acg_agent_platform.models.workflow import (
    Citation,
    ClassificationResult,
    DraftResult,
    Envelope,
    Evidence,
    Run,
    RunState,
    Stage,
    StartRun,
)
from acg_agent_platform.services.approvals import Approvals, Conflict
from acg_agent_platform.services.business import BusinessTools
from acg_agent_platform.services.gateway import (
    BaseModelAdapter,
    BasePolicy,
    ModelGateway,
    PolicyDenied,
)
from acg_agent_platform.services.platform import Platform
from acg_agent_platform.services.store import AccessDenied, Store


class AgentState(TypedDict, total=False):
    run_json: str
    ticket_json: str
    category: str
    source_ids: list[str]
    proposal_id: str
    execution_actor: str
    completed: bool
    business_request: str


class Workflow:
    def __init__(
        self,
        store: Store,
        settings: Settings,
        model: BaseModelAdapter,
        policy: BasePolicy,
    ) -> None:
        self.store, self.settings, self.model, self.policy = (
            store,
            settings,
            model,
            policy,
        )
        self.approvals = Approvals(store.path, settings.approval_seconds)
        self.checkpoint_path = str(store.path) + ".checkpoints.sqlite3"

    @contextmanager
    def _graph(
        self,
    ) -> Iterator[CompiledStateGraph[AgentState, None, AgentState, AgentState]]:
        with SqliteSaver.from_conn_string(self.checkpoint_path) as saver:
            builder = StateGraph(AgentState)
            builder.add_node("classification_agent", self._classification_node)
            builder.add_node("business_specialist", self._business_node)
            builder.add_node("knowledge_tool", self._retrieval_node)
            builder.add_node("evidence_agent", self._draft_node)
            builder.add_node("publish", self._publish)
            builder.add_node("human_review", self._human_review)
            builder.add_node("approved_tool", self._execute)
            builder.add_conditional_edges(
                START,
                self._entry,
                {
                    "it_support": "classification_agent",
                    "business": "business_specialist",
                },
            )
            builder.add_edge("business_specialist", "publish")
            builder.add_conditional_edges(
                "classification_agent",
                self._route,
                {"continue": "knowledge_tool", "stop": "publish"},
            )
            builder.add_conditional_edges(
                "knowledge_tool",
                self._route,
                {"continue": "evidence_agent", "stop": "publish"},
            )
            builder.add_edge("evidence_agent", "publish")
            builder.add_conditional_edges(
                "publish", self._route, {"continue": "human_review", "stop": END}
            )
            builder.add_edge("human_review", "approved_tool")
            builder.add_edge("approved_tool", END)
            yield builder.compile(checkpointer=saver)

    def _config(self, run_id: str) -> RunnableConfig:
        return {
            "configurable": {"thread_id": run_id},
            "recursion_limit": 16,
            "callbacks": [],
        }

    def start(self, principal: Principal, request: StartRun) -> Run:
        profile = Platform(self.store).profile(principal, "it_support")
        ticket = self.store.ticket(principal, request.ticket_id)
        run = Run(
            id=str(uuid4()),
            owner_id=principal.id,
            workspace=principal.workspace,
            ticket_id=ticket.id,
            ticket_version=ticket.version,
            language=request.language,
            state=RunState.AWAITING_REVIEW,
            draft="",
            sources=(),
            model=self.model.name,
            model_calls=0,
            workflow_version="langgraph-it-v1",
            agent_version=profile.version,
            evidence=(),
        )
        with tracing_context(enabled=False), self._graph() as graph:
            result = graph.invoke(
                {
                    "run_json": run.model_dump_json(),
                    "ticket_json": ticket.model_dump_json(),
                    "completed": False,
                },
                self._config(run.id),
                durability="sync",
            )
        return Run.model_validate_json(result["run_json"])

    def inspect(self, principal: Principal, run_id: str) -> dict[str, Any]:
        current = self.store.principal(principal.id)
        with tracing_context(enabled=False), self._graph() as graph:
            snapshot = graph.get_state(self._config(run_id))
            if not snapshot.values:
                raise AccessDenied
            run = Run.model_validate_json(snapshot.values["run_json"])
            if run.owner_id != current.id or run.workspace != current.workspace:
                raise AccessDenied
            if snapshot.values.get("completed"):
                self.approvals.get(current, snapshot.values["proposal_id"])
            else:
                self.store.run(current, run_id)
            return {
                "framework": "langgraph",
                "thread_id": run_id,
                "next": list(snapshot.next),
                "paused": bool(snapshot.interrupts),
                "completed": bool(snapshot.values.get("completed")),
                "nodes": [
                    "classification_agent",
                    "business_specialist",
                    "knowledge_tool",
                    "evidence_agent",
                    "publish",
                    "human_review",
                    "approved_tool",
                ],
            }

    def start_business(
        self, principal: Principal, request: InvoiceRequest | InfrastructureRequest
    ) -> Run:
        principal = self.store.principal(principal.id)
        if isinstance(request, InvoiceRequest):
            # Preflight permission checks before creating an intake ticket.
            for sid in (
                request.order_source_id,
                request.supplier_source_id,
                request.contract_source_id,
            ):
                self.store.source(principal, sid)
            title, case = f"Invoice {request.invoice_id}", "invoice"
        else:
            self.store.source(principal, request.asset_source_id)
            title, case = f"Change request {request.asset_source_id}", "infrastructure"
        profile = Platform(self.store).profile(principal, case)
        ticket = self.store.create_ticket(principal, title, request.model_dump_json())
        run = Run(
            id=str(uuid4()),
            owner_id=principal.id,
            workspace=principal.workspace,
            ticket_id=ticket.id,
            ticket_version=ticket.version,
            language=request.language,
            state=RunState.AWAITING_REVIEW,
            draft="",
            sources=(),
            model="deterministic/business-tools-v1",
            model_calls=0,
            workflow_version="langgraph-business-v1",
            use_case=case,
            agent_version=profile.version,
            evidence=(),
        )
        with tracing_context(enabled=False), self._graph() as graph:
            output = graph.invoke(
                {
                    "run_json": run.model_dump_json(),
                    "ticket_json": ticket.model_dump_json(),
                    "business_request": request.model_dump_json(),
                    "completed": False,
                },
                self._config(run.id),
                durability="sync",
            )
        return Run.model_validate_json(output["run_json"])

    def _entry(self, state: AgentState) -> str:
        return (
            "it_support"
            if Run.model_validate_json(state["run_json"]).use_case == "it_support"
            else "business"
        )

    def _business_node(self, state: AgentState) -> AgentState:
        return self._guard(self._business)(state)

    def _business(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        actor = self.store.principal(run.owner_id)
        tools = BusinessTools(self.store)
        if run.use_case == "invoice":
            report, sources = tools.invoice(
                actor, InvoiceRequest.model_validate_json(state["business_request"])
            )
        else:
            report, sources = tools.infrastructure(
                actor,
                InfrastructureRequest.model_validate_json(state["business_request"]),
            )
        self.policy.inspect(
            Envelope(
                stage=Stage.DRAFT,
                language=run.language,
                text=report,
                classification=Classification.INTERNAL,
            )
        )
        for source in sources:
            if self.store.source(actor, source.id) != source:
                raise PolicyDenied
        run = run.model_copy(
            update={
                "draft": report,
                "sources": tuple(
                    Citation(
                        id=s.id,
                        version=s.version,
                        fingerprint=hashlib.sha256(
                            s.model_dump_json().encode()
                        ).hexdigest(),
                    )
                    for s in sources
                ),
                "evidence": (
                    Evidence(
                        stage=f"{run.use_case}_tools",
                        outcome="review_required",
                        timestamp=time.time(),
                    ),
                ),
            }
        )
        return {"run_json": run.model_dump_json(), "business_request": ""}

    def execute(self, actor: Principal, proposal_id: str) -> Proposal:
        proposal = self.approvals.get(actor, proposal_id)
        if proposal.state != ProposalState.APPROVED:
            raise Conflict("A valid unused approval is required")
        with tracing_context(enabled=False), self._graph() as graph:
            config = self._config(proposal.action.run_id)
            snapshot = graph.get_state(config)
            if not snapshot.values:
                # Legacy v0.2 proposals retain their independently protected executor.
                return self.approvals.execute(actor, proposal_id)
            if snapshot.values.get("completed"):
                raise Conflict("Graph already completed")
            graph.invoke(
                Command(resume={"proposal_id": proposal.id, "actor": actor.id}),
                config,
                durability="sync",
            )
        return self.approvals.get(actor, proposal_id)

    def reconcile(self, actor: Principal, proposal_id: str) -> dict[str, object]:
        """Reconcile only when the action ledger proves execution already committed."""
        proposal = self.approvals.get(actor, proposal_id)
        if proposal.state != ProposalState.EXECUTED:
            raise Conflict("Only an already executed action can be reconciled")
        with tracing_context(enabled=False), self._graph() as graph:
            config = self._config(proposal.action.run_id)
            snapshot = graph.get_state(config)
            if not snapshot.values:
                return {"reconciled": True, "legacy": True}
            if snapshot.values.get("completed"):
                return {"reconciled": True, "already_complete": True}
            if (
                snapshot.next != ("approved_tool",)
                or snapshot.values.get("proposal_id") != proposal_id
            ):
                raise Conflict("Checkpoint needs operator investigation")
            graph.invoke(None, config, durability="sync")
            return {"reconciled": True, "already_complete": False}

    def _classification_node(self, state: AgentState) -> AgentState:
        return self._guard(self._classify)(state)

    def _retrieval_node(self, state: AgentState) -> AgentState:
        return self._guard(self._retrieve)(state)

    def _draft_node(self, state: AgentState) -> AgentState:
        return self._guard(self._draft)(state)

    def _guard(
        self, node: Callable[[AgentState], AgentState]
    ) -> Callable[[AgentState], AgentState]:
        def guarded(state: AgentState) -> AgentState:
            try:
                return node(state)
            except (PolicyDenied, AccessDenied):
                return self._failure(state, RunState.BLOCKED, "policy")
            except (TimeoutError, ValidationError, ValueError, RuntimeError):
                return self._failure(state, RunState.FAILED, "processing")

        return guarded

    def _failure(self, state: AgentState, status: RunState, stage: str) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        run = run.model_copy(
            update={
                "state": status,
                "draft": "",
                "sources": (),
                "evidence": (
                    *run.evidence,
                    Evidence(stage=stage, outcome=status.value, timestamp=time.time()),
                ),
            }
        )
        return {"run_json": run.model_dump_json()}

    def _invoke(self, state: AgentState, envelope: Envelope) -> str:
        run = Run.model_validate_json(state["run_json"])
        gateway = ModelGateway(self.model, self.policy)
        try:
            return gateway.invoke(envelope)
        finally:
            state["run_json"] = run.model_copy(
                update={"model_calls": run.model_calls + gateway.calls}
            ).model_dump_json()

    def _classify(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        principal = self.store.principal(run.owner_id)
        ticket = self.store.ticket(principal, run.ticket_id)
        result = ClassificationResult.model_validate_json(
            self._invoke(
                state,
                Envelope(
                    stage=Stage.CLASSIFY,
                    language=run.language,
                    text=json.dumps(
                        {"title": ticket.title, "description": ticket.description}
                    ),
                    classification=ticket.classification,
                ),
            )
        )
        return {
            "category": result.category.value,
            "run_json": self._event(state, "classify", "allowed"),
        }

    def _retrieve(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        principal = self.store.principal(run.owner_id)
        sources = self.store.sources(principal, state["category"])[
            : min(
                self.settings.max_sources,
                Platform(self.store).profile(principal, "it_support").max_sources,
            )
        ]
        return {
            "source_ids": [s.id for s in sources],
            "run_json": self._event(
                state, "retrieve", "allowed" if sources else "insufficient"
            ),
        }

    def _draft(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        principal = self.store.principal(run.owner_id)
        ticket = self.store.ticket(principal, run.ticket_id)
        sources = tuple(
            self.store.source(principal, sid) for sid in state["source_ids"]
        )
        if not sources:
            prompts = tomllib.loads(
                files("acg_agent_platform")
                .joinpath("resources/prompts.toml")
                .read_text(encoding="utf-8")
            )
            return {
                "run_json": run.model_copy(
                    update={"draft": str(prompts[f"missing_{run.language.value}"])}
                ).model_dump_json()
            }
        classification = (
            Classification.RESTRICTED
            if any(s.classification != Classification.INTERNAL for s in sources)
            else ticket.classification
        )
        context = json.dumps(
            {
                "ticket": json.dumps(
                    {"title": ticket.title, "description": ticket.description}
                ),
                "sources": [
                    {"id": s.id, "version": s.version, "content": s.content}
                    for s in sources
                ],
            }
        )
        result = DraftResult.model_validate_json(
            self._invoke(
                state,
                Envelope(
                    stage=Stage.DRAFT,
                    language=run.language,
                    text=context,
                    classification=classification,
                ),
            )
        )
        for source in sources:
            if self.store.source(principal, source.id) != source:
                raise PolicyDenied
        if (
            self.store.ticket(principal, ticket.id).model_dump_json()
            != state["ticket_json"]
        ):
            raise PolicyDenied
        run = Run.model_validate_json(self._event(state, "draft", "allowed"))
        return {
            "run_json": run.model_copy(
                update={
                    "draft": result.draft,
                    "sources": tuple(
                        Citation(
                            id=s.id,
                            version=s.version,
                            fingerprint=hashlib.sha256(
                                s.model_dump_json().encode()
                            ).hexdigest(),
                        )
                        for s in sources
                    ),
                }
            ).model_dump_json()
        }

    def _publish(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        self.store.save_run(run)
        return {"run_json": run.model_dump_json(), "ticket_json": ""}

    def _human_review(self, state: AgentState) -> AgentState:
        run = Run.model_validate_json(state["run_json"])
        decision = interrupt(
            {
                "run_id": run.id,
                "required": "approved proposal",
                "action": "append_sandbox_note",
            }
        )
        if not isinstance(decision, dict) or set(decision) != {"proposal_id", "actor"}:
            raise Conflict("Invalid graph resume command")
        actor = self.store.principal(str(decision["actor"]))
        proposal = self.approvals.get(actor, str(decision["proposal_id"]))
        if proposal.action.run_id != run.id or proposal.state != ProposalState.APPROVED:
            raise Conflict("Graph resume requires matching approved proposal")
        return {"proposal_id": proposal.id, "execution_actor": actor.id}

    def _execute(self, state: AgentState) -> AgentState:
        actor = self.store.principal(state["execution_actor"])
        proposal = self.approvals.get(actor, state["proposal_id"])
        if proposal.state != ProposalState.EXECUTED:
            self.approvals.execute(actor, proposal.id)
        return {"completed": True}

    def _event(self, state: AgentState, stage: str, outcome: str) -> str:
        run = Run.model_validate_json(state["run_json"])
        return run.model_copy(
            update={
                "evidence": (
                    *run.evidence,
                    Evidence(stage=stage, outcome=outcome, timestamp=time.time()),
                )
            }
        ).model_dump_json()

    def _route(self, state: AgentState) -> str:
        return (
            "continue"
            if Run.model_validate_json(state["run_json"]).state
            == RunState.AWAITING_REVIEW
            else "stop"
        )
