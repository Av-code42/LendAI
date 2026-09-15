"""
Pandas-free single-application feature fetching, for the lite scorer
(app/ml/lite.py). This intentionally duplicates the feature semantics of
app/ml/features.py's pandas-based bulk/training path rather than sharing
code with it, because avoiding a pandas import here is the whole point
(pandas/scipy/scikit-learn/numpy together are the majority of the
deployed function's size -- see backend/README.md's Vercel section).

Because this duplicates logic instead of sharing it, train/serve skew is
a real risk if the two ever drift. scripts/export_lite_models.py guards
against that: it cross-checks the lite scorer's output against the full
sklearn pipeline's output on real historical applications and refuses to
export if they don't match to high precision.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m


def fetch_credit_features(session: Session, application_id: str) -> dict:
    row = _fetch_joined_row(session, application_id)
    return {
        "age": row["age"],
        "monthly_income": row["monthly_income"],
        "employment_tenure_months": row["employment_tenure_months"],
        "bureau_score": row["bureau_score"],
        "active_loans": row["active_loans"],
        "existing_monthly_emi": row["existing_monthly_emi"],
        "foir": row["foir"],
        "requested_amount": row["requested_amount"],
        "tenure_months": row["tenure_months"],
        "avg_monthly_credits": row["avg_monthly_credits"],
        "salary_consistency": row["salary_consistency"],
        "cash_withdrawal_ratio": row["cash_withdrawal_ratio"],
        "monthly_transaction_count": row["monthly_transaction_count"],
        "purpose": row["purpose"],
        "channel": row["channel"],
    }


def fetch_fraud_features(session: Session, application_id: str) -> dict:
    row = _fetch_joined_row(session, application_id)
    doc_agg = _document_aggregates(session, application_id)
    return {
        "device_reuse_count_30d": row["device_reuse_count_30d"] or 0,
        "applications_last_7d": row["applications_last_7d"] or 0,
        "location_mismatch": row["location_mismatch"] or 0,
        "bank_account_age_months": row["bank_account_age_months"] or 0,
        "document_anomaly_score": row["document_anomaly_score"] or 0.0,
        "income_mismatch_score": row["income_mismatch_score"] or 0.0,
        "relationship_months": row["relationship_months"],
        "avg_monthly_credits": row["avg_monthly_credits"],
        "salary_consistency": row["salary_consistency"],
        "cash_withdrawal_ratio": row["cash_withdrawal_ratio"],
        "monthly_transaction_count": row["monthly_transaction_count"],
        "doc_avg_ocr_confidence": doc_agg["doc_avg_ocr_confidence"],
        "doc_max_income_mismatch_ratio": doc_agg["doc_max_income_mismatch_ratio"],
        "doc_any_name_mismatch": doc_agg["doc_any_name_mismatch"],
    }


def _fetch_joined_row(session: Session, application_id: str) -> dict:
    stmt = (
        select(
            m.Application.requested_amount,
            m.Application.tenure_months,
            m.Application.purpose,
            m.Application.channel,
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
        .where(m.Application.application_id == application_id)
    )
    row = session.execute(stmt).mappings().first()
    if row is None:
        raise ValueError(f"No feature data for application {application_id}")
    return dict(row)


def _document_aggregates(session: Session, application_id: str) -> dict:
    stmt = select(
        m.Document.ocr_confidence,
        m.Document.income_mismatch_ratio,
        m.Document.name_match,
    ).where(m.Document.application_id == application_id)
    docs = session.execute(stmt).all()

    if not docs:
        return {
            "doc_avg_ocr_confidence": 1.0,
            "doc_max_income_mismatch_ratio": 0.0,
            "doc_any_name_mismatch": 0,
        }

    ocr_values = [d.ocr_confidence for d in docs if d.ocr_confidence is not None]
    mismatch_values = [d.income_mismatch_ratio for d in docs if d.income_mismatch_ratio is not None]
    any_name_mismatch = any(d.name_match is False for d in docs)

    return {
        "doc_avg_ocr_confidence": (sum(ocr_values) / len(ocr_values)) if ocr_values else 1.0,
        "doc_max_income_mismatch_ratio": max(mismatch_values) if mismatch_values else 0.0,
        "doc_any_name_mismatch": 1 if any_name_mismatch else 0,
    }
