"""
Feature frame construction for the credit and fraud models. Both training
(bulk, from the DB) and live single-application scoring go through these
same functions, so the exact same feature engineering is used in both
places -- no train/serve skew.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m

CREDIT_NUMERIC_FEATURES = [
    "age",
    "monthly_income",
    "employment_tenure_months",
    "bureau_score",
    "active_loans",
    "existing_monthly_emi",
    "foir",
    "requested_amount",
    "tenure_months",
    "avg_monthly_credits",
    "salary_consistency",
    "cash_withdrawal_ratio",
    "monthly_transaction_count",
]
CREDIT_CATEGORICAL_FEATURES = ["purpose", "channel"]

# Per the PRD: device reuse, application velocity, income mismatch,
# location mismatch, document anomaly, account age, transaction
# behaviour, relationship.
FRAUD_NUMERIC_FEATURES = [
    "device_reuse_count_30d",
    "applications_last_7d",
    "location_mismatch",
    "bank_account_age_months",
    "document_anomaly_score",
    "income_mismatch_score",
    "relationship_months",
    "avg_monthly_credits",
    "salary_consistency",
    "cash_withdrawal_ratio",
    "monthly_transaction_count",
    "doc_avg_ocr_confidence",
    "doc_max_income_mismatch_ratio",
    "doc_any_name_mismatch",
]
FRAUD_CATEGORICAL_FEATURES: list[str] = []


def _base_query(session: Session, application_id: str | None = None):
    stmt = (
        select(
            m.Application.application_id,
            m.Application.requested_amount,
            m.Application.tenure_months,
            m.Application.purpose,
            m.Application.channel,
            m.Application.actual_default_label,
            m.Application.actual_fraud_label,
            m.Customer.age,
            m.Customer.monthly_income,
            m.Customer.employment_tenure_months,
            m.Customer.bureau_score,
            m.Customer.active_loans,
            m.Customer.existing_monthly_emi,
            m.Customer.foir,
            m.Customer.relationship_months,
            m.Transaction.avg_monthly_credits,
            m.Transaction.salary_consistency,
            m.Transaction.cash_withdrawal_ratio,
            m.Transaction.monthly_transaction_count,
            m.FraudFeatures.device_reuse_count_30d,
            m.FraudFeatures.applications_last_7d,
            m.FraudFeatures.location_mismatch,
            m.FraudFeatures.bank_account_age_months,
            m.FraudFeatures.document_anomaly_score,
            m.FraudFeatures.income_mismatch_score,
        )
        .join(m.Customer, m.Application.customer_id == m.Customer.customer_id)
        .join(m.Transaction, m.Transaction.customer_id == m.Customer.customer_id)
        .outerjoin(m.FraudFeatures, m.FraudFeatures.application_id == m.Application.application_id)
    )
    if application_id is not None:
        stmt = stmt.where(m.Application.application_id == application_id)
    return stmt


def _document_aggregates(session: Session, application_id: str | None = None) -> pd.DataFrame:
    stmt = select(
        m.Document.application_id,
        m.Document.ocr_confidence,
        m.Document.income_mismatch_ratio,
        m.Document.name_match,
    )
    if application_id is not None:
        stmt = stmt.where(m.Document.application_id == application_id)
    rows = session.execute(stmt).all()
    df = pd.DataFrame(rows, columns=["application_id", "ocr_confidence", "income_mismatch_ratio", "name_match"])
    if df.empty:
        return pd.DataFrame(
            columns=[
                "application_id",
                "doc_avg_ocr_confidence",
                "doc_max_income_mismatch_ratio",
                "doc_any_name_mismatch",
            ]
        )
    agg = df.groupby("application_id").agg(
        doc_avg_ocr_confidence=("ocr_confidence", "mean"),
        doc_max_income_mismatch_ratio=("income_mismatch_ratio", "max"),
        doc_any_name_mismatch=("name_match", lambda s: bool((~s.fillna(True)).any())),
    )
    agg["doc_any_name_mismatch"] = agg["doc_any_name_mismatch"].astype(int)
    return agg.reset_index()


def _load_frame(session: Session, application_id: str | None = None) -> pd.DataFrame:
    rows = session.execute(_base_query(session, application_id)).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    docs = _document_aggregates(session, application_id)
    df = df.merge(docs, on="application_id", how="left")
    df["doc_avg_ocr_confidence"] = df["doc_avg_ocr_confidence"].fillna(1.0)
    df["doc_max_income_mismatch_ratio"] = df["doc_max_income_mismatch_ratio"].fillna(0.0)
    df["doc_any_name_mismatch"] = df["doc_any_name_mismatch"].fillna(0).astype(int)
    return df


def build_credit_training_frame(session: Session) -> tuple[pd.DataFrame, pd.Series]:
    df = _load_frame(session)
    df = df.dropna(subset=["actual_default_label"])
    X = df[CREDIT_NUMERIC_FEATURES + CREDIT_CATEGORICAL_FEATURES]
    y = df["actual_default_label"].astype(int)
    return X, y


def build_fraud_training_frame(session: Session) -> tuple[pd.DataFrame, pd.Series]:
    df = _load_frame(session)
    df = df.dropna(subset=["actual_fraud_label"])
    X = df[FRAUD_NUMERIC_FEATURES + FRAUD_CATEGORICAL_FEATURES]
    y = df["actual_fraud_label"].astype(int)
    return X, y


def build_credit_inference_row(session: Session, application_id: str) -> pd.DataFrame:
    df = _load_frame(session, application_id)
    if df.empty:
        raise ValueError(f"No feature data for application {application_id}")
    return df[CREDIT_NUMERIC_FEATURES + CREDIT_CATEGORICAL_FEATURES]


def build_fraud_inference_row(session: Session, application_id: str) -> pd.DataFrame:
    df = _load_frame(session, application_id)
    if df.empty:
        raise ValueError(f"No feature data for application {application_id}")
    return df[FRAUD_NUMERIC_FEATURES + FRAUD_CATEGORICAL_FEATURES]
