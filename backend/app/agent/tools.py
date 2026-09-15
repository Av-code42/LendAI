"""
Agent tool implementations, one per entry in config/tool_schemas.json.
Every tool function has signature (session, application_id, **kwargs) and
returns a small JSON-serializable result dict -- these are the only
things the agent orchestrator is allowed to do to an application. Tools
are dispatched (and permission/schema validated) exclusively through
app/agent/dispatcher.py; nothing here is called directly by the API layer.

PRD "Agent" section, forbidden list (policy override, threshold changes,
source-data mutation, fraud override, policy-exception approval,
unrestricted disbursal): none of those actions exist as a tool below, so
they are unreachable by construction, not merely blocked by a runtime
check. The runtime check (see dispatcher.py) exists as defense in depth
for a tool name that isn't in this whitelist at all (PRD golden case 8).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.state_machine import require_transition
from app.db import models as m
from app.ml import scoring
from app.ml.fraud_feature_builder import ensure_fraud_features
from app.policy.engine import build_policy_subject, get_policy_config


def _load_tool_schemas() -> dict[str, dict]:
    with open(settings.tool_schemas_path) as f:
        raw = json.load(f)
    return {t["name"]: t for t in raw["tools"]}


TOOL_SCHEMAS: dict[str, dict] = _load_tool_schemas()


def get_customer_profile(session, application_id: str) -> dict:
    app = session.get(m.Application, application_id)
    customer = session.get(m.Customer, app.customer_id)
    return {
        "customer_id": customer.customer_id,
        "age": customer.age,
        "monthly_income": customer.monthly_income,
        "employment_tenure_months": customer.employment_tenure_months,
        "bureau_score": customer.bureau_score,
        "foir": customer.foir,
        "employment_type": customer.employment_type,
    }


def request_document(session, application_id: str, document_type: str, reason: str) -> dict:
    app = session.get(m.Application, application_id)
    if app.status != m.ApplicationStatus.WAITING_FOR_DOCUMENT.value:
        require_transition(app.status, m.ApplicationStatus.WAITING_FOR_DOCUMENT.value)
        app.status = m.ApplicationStatus.WAITING_FOR_DOCUMENT.value
    return {"document_type": document_type, "reason": reason, "status": app.status}


def run_credit_model(session, application_id: str) -> dict:
    output = scoring.score_credit(session, application_id)
    return {
        "score": output.score,
        "risk_level": output.risk_level,
        "model_name": output.model_name,
        "model_version": output.model_version,
    }


def run_fraud_check(session, application_id: str) -> dict:
    ensure_fraud_features(session, application_id)
    output = scoring.score_fraud(session, application_id)
    return {
        "score": output.score,
        "risk_level": output.risk_level,
        "model_name": output.model_name,
        "model_version": output.model_version,
    }


def evaluate_policy(session, application_id: str, policy_version: str) -> dict:
    app = session.get(m.Application, application_id)
    customer = session.get(m.Customer, app.customer_id)
    policy = get_policy_config()
    if policy_version != policy.policy_id:
        raise ValueError(f"Unknown or unsupported policy_version: {policy_version}")
    subject = build_policy_subject(customer, app)
    evaluation = policy.evaluate(subject)
    result = m.PolicyResult(
        application_id=application_id,
        policy_version=evaluation.policy_version,
        overall_pass=evaluation.overall_pass,
        rules=evaluation.to_dict()["rules"],
    )
    session.add(result)
    session.flush()
    return evaluation.to_dict()


def create_human_review(session, application_id: str, reason: str) -> dict:
    require_transition(session.get(m.Application, application_id).status, m.ApplicationStatus.HUMAN_REVIEW.value)
    app = session.get(m.Application, application_id)
    app.status = m.ApplicationStatus.HUMAN_REVIEW.value
    review_id = f"REV{abs(hash((application_id, reason))) % 10_000_000}"
    case = m.HumanReviewCase(
        review_id=review_id,
        application_id=application_id,
        review_reason=reason,
        agent_recommendation="REFER",
        status=m.ReviewStatus.OPEN.value,
    )
    session.add(case)
    session.flush()
    return {"review_id": review_id, "reason": reason}


def generate_offer(session, application_id: str, amount: float, tenure_months: int) -> dict:
    app = session.get(m.Application, application_id)
    require_transition(app.status, m.ApplicationStatus.OFFER.value)
    rate = 13.5
    monthly_rate = rate / 12 / 100
    emi = (amount * monthly_rate * (1 + monthly_rate) ** tenure_months) / (
        (1 + monthly_rate) ** tenure_months - 1
    )
    offer = m.Offer(
        application_id=application_id,
        approved_amount=amount,
        interest_rate_apr=rate,
        tenure_months=tenure_months,
        monthly_installment=round(emi, 2),
        processing_fee=round(amount * 0.01, 2),
        status="PENDING",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(offer)
    app.status = m.ApplicationStatus.OFFER.value
    session.flush()
    return {"offer_id": offer.id, "approved_amount": amount, "monthly_installment": offer.monthly_installment}


TOOL_FUNCTIONS = {
    "get_customer_profile": get_customer_profile,
    "request_document": request_document,
    "run_credit_model": run_credit_model,
    "run_fraud_check": run_fraud_check,
    "evaluate_policy": evaluate_policy,
    "create_human_review": create_human_review,
    "generate_offer": generate_offer,
}
