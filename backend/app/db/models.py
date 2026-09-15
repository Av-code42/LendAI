from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApplicationStatus(str, enum.Enum):
    """The PRD state machine, in order. See app/core/state_machine.py for
    the transition graph -- this enum is just the vocabulary."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DATA_COLLECTION = "DATA_COLLECTION"
    VERIFICATION = "VERIFICATION"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    WAITING_FOR_DOCUMENT = "WAITING_FOR_DOCUMENT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    AUTO_APPROVED = "AUTO_APPROVED"
    DECLINED = "DECLINED"
    OFFER = "OFFER"
    AGREEMENT = "AGREEMENT"
    MOCK_DISBURSAL = "MOCK_DISBURSAL"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ModelType(str, enum.Enum):
    CREDIT = "CREDIT"
    FRAUD = "FRAUD"


class ReviewStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ReviewAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_INFORMATION = "REQUEST_INFORMATION"
    MODIFY_OFFER = "MODIFY_OFFER"
    ESCALATE = "ESCALATE"


class Customer(Base):
    """
    Sourced primarily from the anonymized synthetic customers.csv (no PII
    by design -- see PRD PII-minimisation guardrail). full_name/email/phone
    are populated only for customers created through the live application
    intake API (a real applicant submitting a new loan), and stay NULL for
    the bulk historical/demo dataset.
    """

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    age: Mapped[int] = mapped_column(Integer)
    monthly_income: Mapped[float] = mapped_column(Float)
    employment_tenure_months: Mapped[int] = mapped_column(Integer)
    relationship_months: Mapped[int] = mapped_column(Integer)
    bureau_score: Mapped[int] = mapped_column(Integer)
    active_loans: Mapped[int] = mapped_column(Integer)
    existing_monthly_emi: Mapped[float] = mapped_column(Float)
    foir: Mapped[float] = mapped_column(Float)
    employment_type: Mapped[str] = mapped_column(String, default="SALARIED")

    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    applications: Mapped[list["Application"]] = relationship(back_populates="customer")
    transaction: Mapped["Transaction | None"] = relationship(back_populates="customer", uselist=False)


class Transaction(Base):
    """One row of behavioural banking features per customer (as sourced)."""

    __tablename__ = "transactions"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    avg_monthly_credits: Mapped[float] = mapped_column(Float)
    salary_consistency: Mapped[float] = mapped_column(Float)
    cash_withdrawal_ratio: Mapped[float] = mapped_column(Float)
    monthly_transaction_count: Mapped[int] = mapped_column(Integer)

    customer: Mapped[Customer] = relationship(back_populates="transaction")


class Application(Base):
    __tablename__ = "applications"

    application_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    requested_amount: Mapped[float] = mapped_column(Float)
    tenure_months: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String, default="WEB")
    status: Mapped[str] = mapped_column(String, default=ApplicationStatus.DRAFT.value, index=True)
    policy_version: Mapped[str] = mapped_column(String, default="PL_2026_V1")

    # Ground-truth labels carried over from the historical dataset, used for
    # ML training/evaluation only -- never read by the live decision path.
    actual_default_label: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_fraud_label: Mapped[int | None] = mapped_column(Integer, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped[Customer] = relationship(back_populates="applications")
    documents: Mapped[list["Document"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    fraud_features: Mapped["FraudFeatures | None"] = relationship(back_populates="application", uselist=False)
    model_outputs: Mapped[list["ModelOutput"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    policy_results: Mapped[list["PolicyResult"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    review_cases: Mapped[list["HumanReviewCase"]] = relationship(back_populates="application")
    offers: Mapped[list["Offer"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    agreements: Mapped[list["Agreement"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    agent_events: Mapped[list["AgentEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    document_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    income_mismatch_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    name_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Vercel Blob URL of the actual uploaded file, and whatever fields
    # Textract extracted from it (see app/services/document_extraction.py).
    # Both NULL for historical/bulk-imported documents (no real file ever
    # existed for those) and for live uploads processed by the simulated
    # fallback pipeline (no cloud credentials configured).
    file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="documents")


class FraudFeatures(Base):
    __tablename__ = "fraud_features"

    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), primary_key=True)
    device_reuse_count_30d: Mapped[int] = mapped_column(Integer, default=0)
    applications_last_7d: Mapped[int] = mapped_column(Integer, default=0)
    location_mismatch: Mapped[int] = mapped_column(Integer, default=0)
    bank_account_age_months: Mapped[int] = mapped_column(Integer, default=0)
    document_anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    income_mismatch_score: Mapped[float] = mapped_column(Float, default=0.0)
    fraud_label: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ground truth, training only

    application: Mapped[Application] = relationship(back_populates="fraud_features")


class ModelOutput(Base):
    """
    Append-only score log -- a new row every time a model is invoked, so a
    model_version is stored with every score (PRD requirement) and history
    is never overwritten.
    """

    __tablename__ = "model_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    model_type: Mapped[str] = mapped_column(String)  # CREDIT | FRAUD
    model_name: Mapped[str] = mapped_column(String)  # LOGISTIC_REGRESSION | RANDOM_FOREST | XGBOOST
    model_version: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="model_outputs")


class PolicyResult(Base):
    __tablename__ = "policy_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    policy_version: Mapped[str] = mapped_column(String)
    overall_pass: Mapped[bool] = mapped_column(Boolean)
    rules: Mapped[list[dict]] = mapped_column(JSON)  # rule-level pass/fail + actual + threshold + reason_code
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="policy_results")


class HumanReviewCase(Base):
    __tablename__ = "human_review_cases"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    review_reason: Mapped[str] = mapped_column(String)
    agent_recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=ReviewStatus.OPEN.value)

    # Decision, filled by POST /reviews/{id}/decision. PRD: every decision
    # stores user_id, timestamp, action, reason_code and comment.
    decided_by_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by_user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_action: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_offer_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="review_cases")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    approved_amount: Mapped[float] = mapped_column(Float)
    interest_rate_apr: Mapped[float] = mapped_column(Float)
    tenure_months: Mapped[int] = mapped_column(Integer)
    monthly_installment: Mapped[float] = mapped_column(Float)
    processing_fee: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="offers")


class Agreement(Base):
    __tablename__ = "agreements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    status: Mapped[str] = mapped_column(String, default="PENDING_SIGNATURE")
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="agreements")


class AgentEvent(Base):
    """Immutable log of every agent tool call/result -- the reconstructable
    agent trail required by the PRD."""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)
    tool_name: Mapped[str | None] = mapped_column(String, nullable=True)
    permission: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="agent_events")


class AuditEvent(Base):
    """Immutable audit trail -- every state-changing action, human or
    system, per the PRD's guardrails."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.application_id"), index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped[Application] = relationship(back_populates="audit_events")
