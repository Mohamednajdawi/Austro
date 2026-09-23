"""Compose the synthetic demonstrator API."""

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from acg_agent_platform.config import Provider, Settings
from acg_agent_platform.models.approval import ApprovalRequest, NewTicket, Proposal
from acg_agent_platform.models.business import InfrastructureRequest, InvoiceRequest
from acg_agent_platform.models.platform import (
    AgentProfile,
    AgentRevision,
    ExtractDocument,
    PolicyProbe,
    SourceInput,
)
from acg_agent_platform.models.records import Principal, Source, Ticket
from acg_agent_platform.models.workflow import Run, StartRun
from acg_agent_platform.services.approvals import Approvals, Conflict, Forbidden
from acg_agent_platform.services.content_policy import indicators
from acg_agent_platform.services.documents import extract_document
from acg_agent_platform.services.gateway import (
    BaseModelAdapter,
    BasePolicy,
    FakeModel,
    InternalOnlyPolicy,
)
from acg_agent_platform.services.ollama import OllamaModel
from acg_agent_platform.services.platform import TOOL_CATALOG, Platform
from acg_agent_platform.services.store import AccessDenied, Store
from acg_agent_platform.services.workflow import Workflow

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    model: BaseModelAdapter | None = None,
    policy: BasePolicy | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = Store(settings.database_path)
    adapter = model or (
        OllamaModel(
            settings.ollama_url,
            settings.ollama_model,
            settings.model_timeout,
            openai_compatible=settings.model_provider == Provider.OPENAI_COMPATIBLE,
        )
        if settings.model_provider in (Provider.OLLAMA, Provider.OPENAI_COMPATIBLE)
        else FakeModel()
    )
    approvals = Approvals(settings.database_path, settings.approval_seconds)
    platform = Platform(store)
    workflow = Workflow(
        store,
        settings,
        adapter,
        policy or InternalOnlyPolicy(settings.max_context_chars),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        yield

    app = FastAPI(
        title="ACG synthetic control demonstrator",
        version="0.4.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    assets = Path(__file__).parent / "web"
    app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(assets / "index.html")

    security = HTTPBearer(auto_error=False)

    @app.exception_handler(AccessDenied)
    async def access_error(request: Request, exc: AccessDenied) -> JSONResponse:
        return JSONResponse(
            {"detail": "Not found or no longer authorized"}, status_code=404
        )

    @app.exception_handler(Conflict)
    async def conflict_error(request: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(Forbidden)
    async def forbidden_error(request: Request, exc: Forbidden) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if (origin and origin != expected) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                return JSONResponse(
                    {"detail": "Cross-origin mutation denied"}, status_code=403
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> Principal:
        try:
            if credentials is None:
                raise AccessDenied
            return store.authenticate(credentials.credentials)
        except AccessDenied:
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            ) from None

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.error("Storage unavailable; request blocked")
        return JSONResponse({"detail": "Service unavailable"}, status_code=503)

    @app.get("/api/tickets/{ticket_id}", response_model=Ticket)
    def get_ticket(
        ticket_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Ticket:
        try:
            return store.ticket(principal, ticket_id)
        except AccessDenied:
            raise HTTPException(404, "Not found") from None

    @app.get("/api/me", response_model=Principal)
    def me(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
        return principal

    @app.get("/api/platform")
    def platform_status(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> dict[str, object]:
        return {
            "framework": "LangGraph",
            "version": "0.4.0",
            "tools": TOOL_CATALOG,
            "templates": [
                item.model_dump(mode="json") for item in platform.profiles(principal)
            ],
            "model": adapter.name,
            "processing": "local-only",
            "production_ready": False,
            "connectors": {
                "tickets": "local SQLite",
                "knowledge": "reviewer-published local records",
                "enterprise_identity": "not connected",
                "ERP": "not connected",
                "Microsoft365": "not connected",
                "DLP_SIEM": "not connected",
            },
        }

    @app.get("/api/monitoring")
    def monitoring(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> dict[str, object]:
        return platform.monitoring(principal)

    @app.get("/api/search")
    def search(
        principal: Annotated[Principal, Depends(authenticate)],
        q: str = "",
        source_type: str = "all",
    ) -> tuple[Source, ...]:
        if not 1 <= len(q) <= 200 or source_type not in {
            "all",
            "document",
            "incident",
            "log",
            "email",
            "wiki",
            "business",
        }:
            raise HTTPException(422, "Invalid search parameters")
        return tuple(
            s
            for s in store.all_sources(principal)
            if (source_type == "all" or s.source_type == source_type)
            and q.casefold() in (s.title + " " + s.content).casefold()
        )[:50]

    @app.put("/api/agents", response_model=AgentRevision)
    def configure_agent(
        body: AgentProfile, principal: Annotated[Principal, Depends(authenticate)]
    ) -> AgentRevision:
        return platform.configure(principal, body)

    @app.get("/api/sources", response_model=tuple[Source, ...])
    def list_sources(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> tuple[Source, ...]:
        return store.all_sources(principal)

    @app.post("/api/sources", response_model=Source, status_code=201)
    def publish_source(
        body: SourceInput, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Source:
        return platform.add_source(principal, body)

    @app.delete("/api/sources/{source_id}", response_model=Source)
    def retire_source(
        source_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Source:
        return platform.retire_source(principal, source_id)

    @app.post("/api/documents/extract")
    def extract_file(
        body: ExtractDocument, principal: Annotated[Principal, Depends(authenticate)]
    ) -> dict[str, object]:
        try:
            text = extract_document(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return {
            "text": text,
            "indicators": indicators(text),
            "published": False,
            "notice": "Extracted text is untrusted. Reviewer publication required.",
        }

    @app.post("/api/policy/inspect")
    def inspect_policy(
        body: PolicyProbe, principal: Annotated[Principal, Depends(authenticate)]
    ) -> dict[str, object]:
        found = indicators(body.text)
        allowed = (
            body.destination == "local"
            and body.classification.value == "internal"
            and not (set(found) & {"credential", "private_key"})
        )
        return {
            "allowed": allowed,
            "indicators": found,
            "external_processing_enabled": False,
            "notice": "Heuristic indicators only; not enterprise DLP "
            "or exhaustive PII detection.",
        }

    @app.get("/api/sources/{source_id}", response_model=Source)
    def get_source(
        source_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Source:
        return store.source(principal, source_id)

    @app.get("/api/tickets", response_model=tuple[Ticket, ...])
    def list_tickets(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> tuple[Ticket, ...]:
        return store.tickets(principal)

    @app.post("/api/tickets", response_model=Ticket, status_code=201)
    def new_ticket(
        body: NewTicket, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Ticket:
        return store.create_ticket(principal, body.title, body.description)

    @app.post("/api/runs/{run_id}/proposal", response_model=Proposal, status_code=201)
    def propose(
        run_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Proposal:
        return approvals.propose(principal, run_id)

    @app.get("/api/proposals", response_model=tuple[Proposal, ...])
    def proposal_list(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> tuple[Proposal, ...]:
        return approvals.list(principal)

    @app.get("/api/proposals/{proposal_id}", response_model=Proposal)
    def proposal_get(
        proposal_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Proposal:
        return approvals.get(principal, proposal_id)

    @app.post("/api/proposals/{proposal_id}/approve", response_model=Proposal)
    def approve(
        proposal_id: str,
        body: ApprovalRequest,
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> Proposal:
        return approvals.approve(principal, proposal_id, body.digest)

    @app.post("/api/proposals/{proposal_id}/execute", response_model=Proposal)
    def execute(
        proposal_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Proposal:
        return workflow.execute(principal, proposal_id)

    @app.post("/api/proposals/{proposal_id}/reconcile")
    def reconcile(
        proposal_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> dict[str, object]:
        return workflow.reconcile(principal, proposal_id)

    @app.post("/api/proposals/{proposal_id}/reject", response_model=Proposal)
    def reject(
        proposal_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Proposal:
        return approvals.close(principal, proposal_id, reject=True)

    @app.post("/api/proposals/{proposal_id}/cancel", response_model=Proposal)
    def cancel(
        proposal_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Proposal:
        return approvals.close(principal, proposal_id, reject=False)

    @app.get("/api/model-status")
    def model_status(
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> dict[str, str | bool]:
        return {
            "model": adapter.name,
            "real": isinstance(adapter, OllamaModel),
            "available": adapter.available()
            if isinstance(adapter, OllamaModel)
            else True,
        }

    @app.post("/api/runs", status_code=201, response_model=Run)
    def start_run(
        body: StartRun, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Run:
        try:
            run = workflow.start(principal, body)
            return store.run(principal, run.id)
        except AccessDenied:
            raise HTTPException(404, "Not found") from None

    @app.post("/api/cases/invoice", status_code=201, response_model=Run)
    def invoice_case(
        body: InvoiceRequest, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Run:
        return workflow.start_business(principal, body)

    @app.post("/api/cases/infrastructure", status_code=201, response_model=Run)
    def infrastructure_case(
        body: InfrastructureRequest,
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> Run:
        return workflow.start_business(principal, body)

    @app.get("/api/runs/{run_id}", response_model=Run)
    def get_run(
        run_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> Run:
        try:
            return store.run(principal, run_id)
        except AccessDenied:
            raise HTTPException(404, "Not found") from None

    @app.get("/api/runs/{run_id}/graph")
    def graph_state(
        run_id: str, principal: Annotated[Principal, Depends(authenticate)]
    ) -> dict[str, object]:
        return workflow.inspect(principal, run_id)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "scope": "synthetic-demo"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        real_ready = isinstance(adapter, OllamaModel) and adapter.available()
        return JSONResponse(
            {
                "implementation_can_start": True,
                "agent_workflow_ready": real_ready,
                "synthetic_workflow_ready": True,
                "production_ready": False,
                "stage": "local-pilot" if real_ready else "read-and-draft",
            },
            status_code=200 if real_ready else 503,
        )

    return app
