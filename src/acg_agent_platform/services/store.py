"""Single-host synthetic persistence with explicit authorization boundaries."""

import hashlib
import json
import secrets
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from acg_agent_platform.models.records import (
    Classification,
    Principal,
    Role,
    Source,
    Ticket,
)
from acg_agent_platform.models.workflow import Run


class AccessDenied(Exception):
    """An identity or resource is unavailable to the caller."""


class Store:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise RuntimeError("Unsupported demo database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS principals (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    digest TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
                    expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_profiles (
                    workspace TEXT NOT NULL, template TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(workspace, template, version));
                PRAGMA user_version=3;
            """)

    def seed_demo(self) -> None:
        """Seed only an empty database; never restore revoked users on restart."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM principals").fetchone()[0]:
                return
            for principal in (
                Principal(id="alice", workspace="it", role=Role.SUPPORT),
                Principal(id="reviewer", workspace="it", role=Role.REVIEWER),
                Principal(id="bob", workspace="finance", role=Role.SUPPORT),
            ):
                db.execute(
                    "INSERT INTO principals VALUES (?, ?)",
                    (principal.id, principal.model_dump_json()),
                )
            for ticket in (
                Ticket(
                    id="IT-001",
                    workspace="it",
                    title="VPN support",
                    description="VPN connection fails / VPN-Verbindung fehlt.",
                ),
                Ticket(
                    id="FIN-001",
                    workspace="finance",
                    title="Invoice access",
                    description="Synthetic finance ticket.",
                ),
            ):
                db.execute(
                    "INSERT INTO tickets VALUES (?, ?)",
                    (ticket.id, ticket.model_dump_json()),
                )
            for source in (
                Source(
                    id="KB-VPN",
                    workspace="it",
                    title="VPN checklist",
                    content="Collect the VPN error code / VPN-Fehlercode erfassen.",
                    topic="vpn",
                    allowed_roles=(Role.SUPPORT, Role.REVIEWER),
                ),
                Source(
                    id="KB-RESTRICTED",
                    workspace="it",
                    title="Private operations",
                    content="Restricted synthetic operations details.",
                    topic="vpn",
                    allowed_roles=(Role.REVIEWER,),
                    classification=Classification.RESTRICTED,
                ),
                Source(
                    id="KB-FIN",
                    workspace="finance",
                    title="Finance VPN",
                    content="Finance-only synthetic guidance.",
                    topic="vpn",
                    allowed_roles=(Role.SUPPORT,),
                ),
            ):
                db.execute(
                    "INSERT INTO sources VALUES (?, ?)",
                    (source.id, source.model_dump_json()),
                )

    def issue_session(self, principal_id: str, lifetime: int) -> str:
        """Local administration only; never exposed through an HTTP endpoint."""
        if not 1 <= lifetime <= 3600:
            raise ValueError("Invalid session lifetime")
        self.principal(principal_id)
        token = secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (self._digest(token), principal_id, self.clock() + lifetime),
            )
        return token

    def authenticate(self, token: str) -> Principal:
        with self._connect() as db:
            row = db.execute(
                "SELECT principal_id, expires FROM sessions WHERE digest = ?",
                (self._digest(token),),
            ).fetchone()
        if row is None or float(row[1]) <= self.clock():
            raise AccessDenied
        return self.principal(str(row[0]))

    def principal(self, principal_id: str) -> Principal:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM principals WHERE id = ?", (principal_id,)
            ).fetchone()
        if row is None:
            raise AccessDenied
        principal = Principal.model_validate_json(row[0])
        if not principal.active:
            raise AccessDenied
        return principal

    def set_principal_active(self, principal_id: str, active: bool) -> None:
        principal = self.principal(principal_id)
        with self._connect() as db:
            db.execute(
                "UPDATE principals SET payload = ? WHERE id = ?",
                (
                    principal.model_copy(update={"active": active}).model_dump_json(),
                    principal_id,
                ),
            )

    def ticket(self, principal: Principal, ticket_id: str) -> Ticket:
        current = self.principal(principal.id)
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        if row is None:
            raise AccessDenied
        ticket = Ticket.model_validate_json(row[0])
        if ticket.workspace != current.workspace:
            raise AccessDenied
        if (
            ticket.classification != Classification.INTERNAL
            and current.role != Role.REVIEWER
        ):
            raise AccessDenied
        return ticket

    def sources(self, principal: Principal, topic: str) -> tuple[Source, ...]:
        current = self.principal(principal.id)
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM sources ORDER BY id").fetchall()
        sources = (Source.model_validate_json(row[0]) for row in rows)
        return tuple(
            source
            for source in sources
            if source.active
            and source.workspace == current.workspace
            and current.role in source.allowed_roles
            and source.topic == topic
        )

    def put_source(self, source: Source) -> None:
        """Local connector administration only, not a user-facing mutation."""
        with self._connect() as db:
            db.execute(
                "INSERT INTO sources VALUES (?, ?) ON CONFLICT(id) "
                "DO UPDATE SET payload = excluded.payload",
                (source.id, source.model_dump_json()),
            )

    def tickets(self, principal: Principal) -> tuple[Ticket, ...]:
        with self._connect() as db:
            ids = db.execute("SELECT id FROM tickets ORDER BY id").fetchall()
        result = []
        for row in ids:
            try:
                result.append(self.ticket(principal, row[0]))
            except AccessDenied:
                continue
        return tuple(result)

    def create_ticket(
        self, principal: Principal, title: str, description: str
    ) -> Ticket:
        from uuid import uuid4

        current = self.principal(principal.id)
        ticket = Ticket(
            id=f"IT-{uuid4().hex[:12]}",
            workspace=current.workspace,
            title=title,
            description=description,
        )
        with self._connect() as db:
            db.execute(
                "INSERT INTO tickets VALUES (?, ?)",
                (ticket.id, ticket.model_dump_json()),
            )
        return ticket

    def add_knowledge_examples(self) -> None:
        """Explicit local setup never overwrites existing source permissions."""
        examples = (
            Source(
                id="KB-ACCOUNT",
                workspace="it",
                title="Account support policy",
                topic="account",
                allowed_roles=(Role.SUPPORT, Role.REVIEWER),
                content="Verify the requester through the approved identity process. "
                "Record the account name and exact error. "
                "Never record passwords or MFA codes. "
                "Password resets and permission changes require authorized IT review.",
            ),
            Source(
                id="KB-NETWORK",
                workspace="it",
                title="Network diagnostic checklist",
                topic="network",
                allowed_roles=(Role.SUPPORT, Role.REVIEWER),
                content="Record the affected device, connection type, time and scope. "
                "Check whether other approved services are reachable. "
                "Do not change firewall, DNS or production configuration "
                "without approval.",
            ),
        )
        with self._connect() as db:
            for source in examples:
                db.execute(
                    "INSERT OR IGNORE INTO sources VALUES (?, ?)",
                    (source.id, source.model_dump_json()),
                )

    def seed_business_examples(self) -> None:
        """Provision synthetic business references without overwriting existing data."""
        from datetime import date

        examples = [
            (
                "PO-100",
                "finance",
                "purchase_order",
                {
                    "kind": "purchase_order",
                    "supplier_id": "SUP-01",
                    "total": "10000.00",
                    "currency": "EUR",
                    "cost_center": "FIN-OPS",
                },
            ),
            (
                "SUP-01",
                "finance",
                "supplier",
                {
                    "kind": "supplier",
                    "supplier_id": "SUP-01",
                    "bank_account": "AT611904300234573201",
                },
            ),
            (
                "CON-100",
                "finance",
                "contract",
                {
                    "kind": "contract",
                    "supplier_id": "SUP-01",
                    "ceiling": "10000.00",
                    "currency": "EUR",
                },
            ),
            (
                "ASSET-EDGE",
                "it",
                "asset",
                {
                    "kind": "asset",
                    "name": "Sandbox edge router",
                    "depends_on": [],
                    "safety_critical": False,
                    "updated_at": date.today().isoformat(),
                },
            ),
            (
                "ASSET-APP",
                "it",
                "asset",
                {
                    "kind": "asset",
                    "name": "Sandbox application",
                    "depends_on": ["ASSET-EDGE"],
                    "safety_critical": False,
                    "updated_at": date.today().isoformat(),
                },
            ),
        ]
        with self._connect() as db:
            principal = Principal(
                id="finance-reviewer", workspace="finance", role=Role.REVIEWER
            )
            db.execute(
                "INSERT OR IGNORE INTO principals VALUES (?, ?)",
                (principal.id, principal.model_dump_json()),
            )
            for sid, workspace, topic, content in examples:
                source = Source(
                    id=sid,
                    workspace=workspace,
                    title=sid,
                    content=json.dumps(content),
                    topic=topic,
                    allowed_roles=(Role.SUPPORT, Role.REVIEWER),
                )
                db.execute(
                    "INSERT OR IGNORE INTO sources VALUES (?, ?)",
                    (source.id, source.model_dump_json()),
                )

    def all_sources(self, principal: Principal) -> tuple[Source, ...]:
        current = self.principal(principal.id)
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM sources ORDER BY id").fetchall()
        sources = (Source.model_validate_json(row[0]) for row in rows)
        return tuple(
            s
            for s in sources
            if s.active
            and s.workspace == current.workspace
            and current.role in s.allowed_roles
        )

    def source(self, principal: Principal, source_id: str) -> Source:
        current = self.principal(principal.id)
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        if row is None:
            raise AccessDenied
        source = Source.model_validate_json(row[0])
        if (
            not source.active
            or source.workspace != current.workspace
            or current.role not in source.allowed_roles
        ):
            raise AccessDenied
        return source

    def save_run(self, run: Run) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?, ?) ON CONFLICT(id) DO NOTHING",
                (run.id, run.model_dump_json()),
            )

    def run(self, principal: Principal, run_id: str) -> Run:
        current = self.principal(principal.id)
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise AccessDenied
        run = Run.model_validate_json(row[0])
        if run.workspace != current.workspace or run.owner_id != current.id:
            raise AccessDenied
        ticket = self.ticket(current, run.ticket_id)
        if ticket.version != run.ticket_version:
            raise AccessDenied
        for citation in run.sources:
            source = self.source(current, citation.id)
            if (
                source.version != citation.version
                or source.classification != Classification.INTERNAL
                or (
                    citation.fingerprint
                    and self._digest(source.model_dump_json()) != citation.fingerprint
                )
            ):
                raise AccessDenied
        return run

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
