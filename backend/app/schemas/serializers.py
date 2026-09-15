"""
Builds the composed API response shapes (e.g. "latest credit score",
"current offer") from the underlying append-only/one-to-many ORM
relationships. Kept separate from the Pydantic schema definitions so the
"what counts as latest" logic lives in exactly one place.
"""

from __future__ import annotations

from app.db import models as m


def _latest(items: list, key: str):
    if not items:
        return None
    return max(items, key=lambda i: getattr(i, key))


def serialize_application(app: m.Application) -> dict:
    credit_outputs = [o for o in app.model_outputs if o.model_type == m.ModelType.CREDIT.value]
    fraud_outputs = [o for o in app.model_outputs if o.model_type == m.ModelType.FRAUD.value]

    return {
        "application_id": app.application_id,
        "customer_id": app.customer_id,
        "customer": {
            "customer_id": app.customer.customer_id,
            "full_name": app.customer.full_name,
            "email": app.customer.email,
            "phone": app.customer.phone,
        },
        "status": app.status,
        "requested_amount": app.requested_amount,
        "tenure_months": app.tenure_months,
        "purpose": app.purpose,
        "policy_version": app.policy_version,
        "submitted_at": app.submitted_at,
        "created_at": app.created_at,
        "updated_at": app.updated_at,
        "documents": app.documents,
        "latest_credit_score": _latest(credit_outputs, "scored_at"),
        "latest_fraud_score": _latest(fraud_outputs, "scored_at"),
        "policy_result": _latest(app.policy_results, "evaluated_at"),
        "offer": _latest(app.offers, "created_at"),
        "agreement": _latest(app.agreements, "created_at"),
    }
