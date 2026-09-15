"""Pydantic request/response schemas for the API layer. Response models
mirror the frontend's existing domain types (src/types/domain.ts) closely
so a future frontend swap from its mock worker to this backend is a
base-URL change, not a rewrite."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


# --- customers / applications -------------------------------------------------


class CustomerSummary(ORMModel):
    customer_id: str
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class ApplicationCreate(BaseModel):
    full_name: str = Field(min_length=2)
    email: str
    phone: str
    monthly_income: float = Field(gt=0)
    age: int = Field(ge=18, le=100)
    employment_tenure_months: int = Field(ge=0)
    relationship_months: int = Field(ge=0, default=0, description="Months banking with us -- MVP scope is existing customers (PRD), so this should normally be > 0.")
    bureau_score: int = Field(ge=300, le=900)
    active_loans: int = Field(ge=0, default=0)
    existing_monthly_emi: float = Field(ge=0, default=0)
    requested_amount: float = Field(gt=0)
    tenure_months: int = Field(ge=6, le=60)
    purpose: str
    channel: str = "WEB"


class ApplicationPatch(BaseModel):
    requested_amount: float | None = Field(default=None, gt=0)
    tenure_months: int | None = Field(default=None, ge=6, le=60)
    purpose: str | None = None


class PolicyResultOut(ORMModel):
    id: int
    application_id: str
    policy_version: str
    overall_pass: bool
    rules: list[dict]
    evaluated_at: datetime


class ModelOutputOut(ORMModel):
    id: int
    application_id: str
    model_type: str
    model_name: str
    model_version: str
    score: float
    risk_level: str
    scored_at: datetime


class DocumentOut(ORMModel):
    id: int
    application_id: str
    document_type: str
    status: str
    ocr_confidence: float | None
    income_mismatch_ratio: float | None
    name_match: bool | None
    file_name: str | None
    uploaded_at: datetime


class DocumentCreate(BaseModel):
    document_type: str
    file_name: str = "document.pdf"


class OfferOut(ORMModel):
    id: int
    application_id: str
    approved_amount: float
    interest_rate_apr: float
    tenure_months: int
    monthly_installment: float
    processing_fee: float
    status: str
    expires_at: datetime
    created_at: datetime


class AgreementOut(ORMModel):
    id: int
    application_id: str
    status: str
    signed_at: datetime | None
    document_url: str | None


class ApplicationOut(ORMModel):
    application_id: str
    customer_id: str
    customer: CustomerSummary
    status: str
    requested_amount: float
    tenure_months: int
    purpose: str
    policy_version: str
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentOut] = []
    latest_credit_score: ModelOutputOut | None = None
    latest_fraud_score: ModelOutputOut | None = None
    policy_result: PolicyResultOut | None = None
    offer: OfferOut | None = None
    agreement: AgreementOut | None = None


class AgentEventOut(ORMModel):
    id: int
    application_id: str
    step: int
    type: str
    tool_name: str | None
    permission: str | None
    detail: str
    payload: dict | None
    created_at: datetime


class AuditEventOut(ORMModel):
    id: int
    application_id: str
    actor: str
    action: str
    detail: str
    created_at: datetime


# --- reviews -------------------------------------------------------------


class HumanReviewCaseOut(ORMModel):
    review_id: str
    application_id: str
    application: ApplicationOut
    status: str
    review_reason: str
    agent_recommendation: str | None
    decision_action: str | None
    decision_reason_code: str | None
    decision_comment: str | None
    decided_by_user_id: str | None
    decided_by_user_name: str | None
    modified_offer_amount: float | None
    decided_at: datetime | None
    created_at: datetime


class ReviewDecisionIn(BaseModel):
    user_id: str
    user_name: str
    action: str = Field(pattern="^(APPROVE|REJECT|REQUEST_INFORMATION|MODIFY_OFFER|ESCALATE)$")
    reason_code: str
    comment: str = Field(min_length=1)
    modified_offer_amount: float | None = None
