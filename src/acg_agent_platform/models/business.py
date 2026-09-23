"""Strict business records; amounts are decimal strings, never model arithmetic."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from acg_agent_platform.models.records import Record
from acg_agent_platform.models.workflow import Language

Money = Annotated[str, Field(strict=True, pattern=r"^(0|[1-9]\d{0,10})\.\d{2}$")]
Identifier = Annotated[
    str, Field(strict=True, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class PurchaseOrder(Record):
    kind: Literal["purchase_order"] = "purchase_order"
    supplier_id: Identifier
    total: Money
    currency: Literal["EUR", "USD", "GBP"] = "EUR"
    cost_center: str = Field(min_length=1, max_length=80)


class Supplier(Record):
    kind: Literal["supplier"] = "supplier"
    supplier_id: Identifier
    bank_account: str = Field(min_length=10, max_length=40)


class Contract(Record):
    kind: Literal["contract"] = "contract"
    supplier_id: Identifier
    ceiling: Money
    currency: Literal["EUR", "USD", "GBP"] = "EUR"


class Asset(Record):
    kind: Literal["asset"] = "asset"
    name: str = Field(min_length=1, max_length=120)
    depends_on: tuple[Identifier, ...] = Field(default=(), max_length=100)
    safety_critical: bool = False
    updated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class InvoiceRequest(Record):
    invoice_id: Identifier
    supplier_id: Identifier
    order_source_id: Identifier
    supplier_source_id: Identifier
    contract_source_id: Identifier
    net: Money
    vat: Money
    total: Money
    currency: Literal["EUR", "USD", "GBP"] = "EUR"
    bank_account: str = Field(min_length=10, max_length=40)
    language: Language = Language.EN

    def difference(self, amount: str) -> Decimal:
        return Decimal(self.total) - Decimal(amount)


class InfrastructureRequest(Record):
    asset_source_id: Identifier
    request: str = Field(strict=True, min_length=8, max_length=4000)
    language: Language = Language.EN
