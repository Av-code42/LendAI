from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.tools import generate_offer
from app.core.audit import log_audit
from app.core.state_machine import InvalidTransitionError, require_transition
from app.db import models as m
from app.db.base import get_db
from app.schemas.api import HumanReviewCaseOut, ReviewDecisionIn
from app.schemas.serializers import serialize_application
from app.schemas.api import ApplicationOut

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _review_relations_stmt():
    return select(m.HumanReviewCase).options(
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.customer),
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.documents),
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.model_outputs),
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.policy_results),
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.offers),
        selectinload(m.HumanReviewCase.application).selectinload(m.Application.agreements),
    )


def _out(case: m.HumanReviewCase) -> HumanReviewCaseOut:
    data = {
        "review_id": case.review_id,
        "application_id": case.application_id,
        "application": ApplicationOut.model_validate(serialize_application(case.application)),
        "status": case.status,
        "review_reason": case.review_reason,
        "agent_recommendation": case.agent_recommendation,
        "decision_action": case.decision_action,
        "decision_reason_code": case.decision_reason_code,
        "decision_comment": case.decision_comment,
        "decided_by_user_id": case.decided_by_user_id,
        "decided_by_user_name": case.decided_by_user_name,
        "modified_offer_amount": case.modified_offer_amount,
        "decided_at": case.decided_at,
        "created_at": case.created_at,
    }
    return HumanReviewCaseOut.model_validate(data)


@router.get("", response_model=list[HumanReviewCaseOut])
def list_reviews(db: Session = Depends(get_db)):
    cases = db.execute(_review_relations_stmt().order_by(m.HumanReviewCase.created_at.desc()).limit(200)).scalars().all()
    return [_out(c) for c in cases]


@router.get("/{review_id}", response_model=HumanReviewCaseOut)
def get_review(review_id: str, db: Session = Depends(get_db)):
    case = db.execute(_review_relations_stmt().where(m.HumanReviewCase.review_id == review_id)).scalars().first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"Review case {review_id} not found")
    return _out(case)


@router.post("/{review_id}/decision", response_model=HumanReviewCaseOut)
def decide_review(review_id: str, payload: ReviewDecisionIn, db: Session = Depends(get_db)):
    case = db.execute(_review_relations_stmt().where(m.HumanReviewCase.review_id == review_id)).scalars().first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"Review case {review_id} not found")
    if case.status != m.ReviewStatus.OPEN.value:
        raise HTTPException(status_code=409, detail="This review case has already been decided")

    app = case.application

    try:
        if payload.action == "APPROVE":
            require_transition(app.status, m.ApplicationStatus.OFFER.value)
            generate_offer(db, app.application_id, amount=app.requested_amount, tenure_months=app.tenure_months)
        elif payload.action == "REJECT":
            require_transition(app.status, m.ApplicationStatus.DECLINED.value)
            app.status = m.ApplicationStatus.DECLINED.value
        elif payload.action == "REQUEST_INFORMATION":
            require_transition(app.status, m.ApplicationStatus.WAITING_FOR_DOCUMENT.value)
            app.status = m.ApplicationStatus.WAITING_FOR_DOCUMENT.value
        elif payload.action == "MODIFY_OFFER":
            if not payload.modified_offer_amount:
                raise HTTPException(status_code=422, detail="modified_offer_amount is required for MODIFY_OFFER")
            if payload.modified_offer_amount > app.requested_amount:
                raise HTTPException(status_code=422, detail="Modified offer cannot exceed the requested amount (must stay within policy)")
            require_transition(app.status, m.ApplicationStatus.OFFER.value)
            generate_offer(db, app.application_id, amount=payload.modified_offer_amount, tenure_months=app.tenure_months)
        elif payload.action == "ESCALATE":
            require_transition(app.status, m.ApplicationStatus.HUMAN_REVIEW.value)
            app.status = m.ApplicationStatus.HUMAN_REVIEW.value
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    case.decided_by_user_id = payload.user_id
    case.decided_by_user_name = payload.user_name
    case.decision_action = payload.action
    case.decision_reason_code = payload.reason_code
    case.decision_comment = payload.comment
    case.modified_offer_amount = payload.modified_offer_amount
    case.decided_at = datetime.now(timezone.utc)
    if payload.action != "ESCALATE":
        case.status = m.ReviewStatus.CLOSED.value

    log_audit(
        db,
        app.application_id,
        payload.user_name,
        f"REVIEW_{payload.action}",
        f"{payload.comment} (reason: {payload.reason_code})",
    )
    db.commit()
    case = db.execute(_review_relations_stmt().where(m.HumanReviewCase.review_id == review_id)).scalars().first()
    return _out(case)
