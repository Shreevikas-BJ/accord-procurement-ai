import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, le=Decimal("100000000000"), decimal_places=6, allow_inf_nan=False)]
Cost = Annotated[Decimal, Field(ge=0, le=Decimal("100000000000"), decimal_places=4, allow_inf_nan=False)]
Quantity = Annotated[Decimal, Field(gt=0, le=Decimal("1000000000"), decimal_places=4, allow_inf_nan=False)]
Confidence = Annotated[Decimal, Field(ge=0, le=1)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    source_text: str = Field(max_length=4000)
    confidence: Confidence = Decimal("1")
    bounding_box: list[float] | None = None
    evidence_type: Literal["text", "ocr", "visual", "missing"] = "text"
    evidence_strength: Literal["strong", "weak", "unsupported"] = "weak"
    source_status: Literal["PRESENT", "NOT_FOUND", "AMBIGUOUS", "EXTRACTION_FAILED"] = "PRESENT"
    sheet: str | None = None
    row: int | None = None
    cell: str | None = None
    table: int | None = None
    decision_status: Literal["ACCEPTED", "REVIEW_REQUIRED", "REJECTED", "NOT_FOUND"] = "ACCEPTED"
    reason: str | None = Field(default=None, max_length=1000)
    raw_candidate: str | None = Field(default=None, max_length=4000)
    accepted_value: str | None = Field(default=None, max_length=4000)


class PriceTier(Strict):
    minimum: Quantity
    maximum: Quantity | None = None
    unit_price: Money

    @model_validator(mode="after")
    def valid_range(self):
        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("Tier maximum must be greater than or equal to its minimum")
        return self


class LineItemExtraction(Strict):
    supplier_sku: str | None = Field(default=None, min_length=1, max_length=200)
    manufacturer_part_number: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    quantity: Quantity | None = None
    uom: str | None = None
    unit_price: Money | None = None
    moq: Cost | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    lead_time_min: int | None = Field(default=None, ge=0, le=3650)
    delivery_date: date | None = None
    stated_line_total: Cost | None = None
    confidence: Confidence = Decimal("0.5")
    source_references: dict[str, Evidence] = Field(default_factory=dict)
    price_tiers: list[PriceTier] = Field(default_factory=list, max_length=30)

    @field_validator("lead_time_days", mode="before")
    @classmethod
    def normalize_lead(cls, value):
        if isinstance(value, str) and re.search(r"day|week", value, re.I):
            numbers = re.findall(r"\d+", value)
            if not numbers:
                raise ValueError("Lead time must contain a number")
            return max(map(int, numbers)) * (7 if "week" in value.lower() else 1)
        return value


class QuoteExtraction(Strict):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=300)
    supplier_email: str | None = None
    quote_number: str | None = Field(default=None, min_length=1, max_length=200)
    rfq_number: str | None = None
    quote_date: date | None = None
    expiration_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    payment_terms: str | None = None
    shipping_terms: str | None = None
    shipping_cost: Cost | None = None
    tax: Cost | None = None
    stated_subtotal: Cost | None = None
    stated_total: Cost | None = None
    notes: str | None = None
    confidence: Confidence = Decimal("0.5")
    source_references: dict[str, Evidence] = Field(default_factory=dict)
    line_items: list[LineItemExtraction] = Field(min_length=1, max_length=500)


class ReviewLine(LineItemExtraction):
    id: str
    item_id: str | None = None


class Review(QuoteExtraction):
    version: int
    supplier_id: str | None = None
    rfq_id: str | None = None
    line_items: list[ReviewLine] = Field(min_length=1, max_length=500)
    confirm_review: bool = False
    confirmed_fields: list[str] = Field(default_factory=list, max_length=1000)


class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SettingsInput(Strict):
    price_weight: int = Field(ge=0, le=100)
    lead_time_weight: int = Field(ge=0, le=100)
    reliability_weight: int = Field(ge=0, le=100)
    fit_weight: int = Field(ge=0, le=100)
    anomaly_threshold: Decimal = Field(ge=0, le=1)
    lead_time_behavior: Literal["conservative"] = "conservative"
    organization_name: str = Field(min_length=2, max_length=200)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def weights(self):
        if self.price_weight + self.lead_time_weight + self.reliability_weight + self.fit_weight != 100:
            raise ValueError("Scoring weights must sum to 100")
        return self


class DraftInput(Strict):
    quote_id: str
    kind: Literal["Negotiation", "Missing Information", "Updated Lead Time", "Revised Pricing", "Follow-Up"] = (
        "Negotiation"
    )


class DraftEdit(Strict):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)
    status: Literal["Draft", "Approved"] = "Draft"


class ApprovalInput(Strict):
    recommendation_id: str
    note: str = Field(min_length=3, max_length=2000)


class PasteInput(Strict):
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=20, max_length=100000)
    rfq_id: str | None = None


class UserInput(Strict):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["Admin", "Buyer", "Viewer"]


class ItemInput(Strict):
    sku: str = Field(min_length=1, max_length=100)
    manufacturer_part_number: str = Field(max_length=100)
    description: str = Field(min_length=2, max_length=1000)
    category: str = Field(min_length=2, max_length=100)
    uom: str = Field(min_length=1, max_length=20)
