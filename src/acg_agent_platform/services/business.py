"""Deterministic business tools used by LangGraph specialist nodes."""

from datetime import date
from decimal import Decimal

from acg_agent_platform.models.business import (
    Asset,
    Contract,
    InfrastructureRequest,
    InvoiceRequest,
    PurchaseOrder,
    Supplier,
)
from acg_agent_platform.models.records import Classification, Principal, Source
from acg_agent_platform.services.gateway import PolicyDenied
from acg_agent_platform.services.store import Store


class BusinessTools:
    def __init__(self, store: Store) -> None:
        self.store = store

    def invoice(
        self, actor: Principal, request: InvoiceRequest
    ) -> tuple[str, tuple[Source, ...]]:
        sources = tuple(
            self.store.source(actor, sid)
            for sid in (
                request.order_source_id,
                request.supplier_source_id,
                request.contract_source_id,
            )
        )
        self._internal(sources)
        order = PurchaseOrder.model_validate_json(sources[0].content)
        supplier = Supplier.model_validate_json(sources[1].content)
        contract = Contract.model_validate_json(sources[2].content)
        findings: list[str] = []
        if Decimal(request.net) + Decimal(request.vat) != Decimal(request.total):
            findings.append("VAT/arithmetic mismatch: net + VAT does not equal total.")
        if any(
            sid != request.supplier_id
            for sid in (order.supplier_id, supplier.supplier_id, contract.supplier_id)
        ):
            findings.append("Supplier mismatch; independent verification required.")
        if request.currency != order.currency or request.currency != contract.currency:
            findings.append(
                "Currency mismatch; no cross-currency comparison performed."
            )
        else:
            delta = request.difference(order.total)
            if delta:
                findings.append(
                    f"Purchase-order difference: {delta:.2f} {request.currency}."
                )
            if Decimal(request.total) > Decimal(contract.ceiling):
                findings.append("Contract ceiling exceeded.")
        if (
            request.bank_account.replace(" ", "").upper()
            != supplier.bank_account.replace(" ", "").upper()
        ):
            findings.append(
                "Bank details differ: verify through the supplier master-data process."
            )
        # Visible local intake duplicates only; not an ERP-wide guarantee.
        matches = [
            t
            for t in self.store.tickets(actor)
            if t.title == f"Invoice {request.invoice_id}"
        ]
        if len(matches) > 1:
            findings.append(
                "Possible duplicate invoice intake; check existing review records."
            )
        heading = (
            "Rechnungsprüfung" if request.language.value == "de" else "Invoice review"
        )
        report = (
            f"{heading}: {request.invoice_id}\n"
            f"Amount: {request.total} {request.currency}\n"
            f"Proposed cost center: {order.cost_center}\n\n"
            + "\n".join(
                findings
                or [
                    "No mismatch found in supplied fields; "
                    "this is not financial approval."
                ]
            )
            + "\n\nSources: "
            + ", ".join(f"[{s.id}] v{s.version}" for s in sources)
            + "\nNo payment, posting or supplier master-data change. "
            "Technical and commercial review required."
        )
        return report, sources

    def infrastructure(
        self, actor: Principal, request: InfrastructureRequest
    ) -> tuple[str, tuple[Source, ...]]:
        target = self.store.source(actor, request.asset_source_id)
        self._internal((target,))
        Asset.model_validate_json(target.content)
        visible = self.store.sources(actor, "asset")
        self._internal(visible)
        if len(visible) > 200:
            raise ValueError("Asset scope exceeds pilot limit")
        assets = {
            source.id: Asset.model_validate_json(source.content) for source in visible
        }
        if target.id not in assets:
            raise ValueError("Target is not an authoritative asset record")
        affected = {target.id}
        for _ in range(len(assets)):
            expanded = affected | {
                sid
                for sid, asset in assets.items()
                if any(dependency in affected for dependency in asset.depends_on)
            }
            if expanded == affected:
                break
            affected = expanded
        findings = [f"[{sid}] {assets[sid].name}" for sid in sorted(affected)]
        stale = [
            sid
            for sid in affected
            if (date.today() - date.fromisoformat(assets[sid].updated_at)).days > 90
            or date.fromisoformat(assets[sid].updated_at) > date.today()
        ]
        if stale:
            findings.append(
                "Stale or future-dated records: " + ", ".join(sorted(stale))
            )
        if any(dep not in assets for sid in affected for dep in assets[sid].depends_on):
            findings.append(
                "Incomplete dependency coverage: "
                "one or more references are unavailable."
            )
        if any(assets[sid].safety_critical for sid in affected):
            findings.append(
                "Safety-critical dependency: formal safety/change review required."
            )
        heading = (
            "Infrastrukturplanung"
            if request.language.value == "de"
            else "Infrastructure change planning"
        )
        report = (
            f"{heading}\nRequest (untrusted): {request.request}\n\n"
            "Affected assets in the authorized local database:\n"
            + "\n".join(findings)
            + "\n\nPrepare a change window, owner, validation plan "
            "and rollback plan for review."
            "\nThis is a bounded database dependency analysis, "
            "not proof of complete topology."
            "\nNo production change executed; only a review package can be filed."
        )
        # All traversed records are dependencies of the analysis, even unaffected ones.
        return report, tuple(visible)

    @staticmethod
    def _internal(sources: tuple[Source, ...]) -> None:
        if any(source.classification != Classification.INTERNAL for source in sources):
            raise PolicyDenied
