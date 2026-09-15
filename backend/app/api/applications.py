from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.orchestrator import AgentRunNotAllowedError, run_agent
from app.core.audit import log_audit
from app.core.document_pipeline import process_document
from app.core.state_machine import InvalidTransitionError, require_transition
from app.db import models as m
from app.db.base import get_db
from app.ml import scoring
from app.ml.fraud_feature_builder import ensure_fraud_features
from app.policy.engine import build_policy_subject, get_policy_config
from app.schemas.api import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationPatch,
    DocumentOut,
    ModelOutputOut,
    OfferOut,
    PolicyResultOut,
)
from app.schemas.serializers import serialize_application

router = APIRouter(prefix="/applications", tags=["applications"])


def _app_with_relations(db: Session, application_id: str) -> m.Application:
    stmt = (
        select(m.Application)
        .where(m.Application.application_id == application_id)
        .options(
            selectinload(m.Application.customer),
            selectinload(m.Application.documents),
            selectinload(m.Application.model_outputs),
            selectinload(m.Application.policy_results),
            selectinload(m.Application.offers),
            selectinload(m.Application.agreements),
        )
    )
    app = db.execute(stmt).scalars().first()
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return app


def _out(app: m.Application) -> ApplicationOut:
    return ApplicationOut.model_validate(serialize_application(app))


def _next_application_id(db: Session) -> str:
    # Historical rows are APP2000xx; live ones get a distinct, still-sortable
    # prefix so the two populations are trivially distinguishable.
    count = db.execute(select(m.Application)).scalars().all()
    return f"APPLIVE{len(count) + 1:06d}"


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    stmt = select(m.Application).options(
        selectinload(m.Application.customer),
        selectinload(m.Application.documents),
        selectinload(m.Application.model_outputs),
        selectinload(m.Application.policy_results),
        selectinload(m.Application.offers),
        selectinload(m.Application.agreements),
    ).order_by(m.Application.updated_at.desc()).limit(200)
    apps = db.execute(stmt).scalars().all()
    return [_out(a) for a in apps]


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    existing_count = db.execute(select(m.Customer)).scalars().all()
    customer = m.Customer(
        customer_id=f"CUSLIVE{len(existing_count) + 1:06d}",
        age=payload.age,
        monthly_income=payload.monthly_income,
        employment_tenure_months=payload.employment_tenure_months,
        relationship_months=payload.relationship_months,
        bureau_score=payload.bureau_score,
        active_loans=payload.active_loans,
        existing_monthly_emi=payload.existing_monthly_emi,
        foir=round(payload.existing_monthly_emi / payload.monthly_income, 4) if payload.monthly_income else 0.0,
        employment_type="SALARIED",
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(customer)
    db.flush()

    # New live customers have no transaction history yet -- insert neutral
    # placeholder behavioural features so the credit/fraud feature frames
    # (which join against transactions) don't break for brand-new
    # applicants. A real system would backfill this from core banking.
    db.add(
        m.Transaction(
            customer_id=customer.customer_id,
            avg_monthly_credits=payload.monthly_income,
            salary_consistency=1.0,
            cash_withdrawal_ratio=0.1,
            monthly_transaction_count=15,
        )
    )

    app = m.Application(
        application_id=_next_application_id(db),
        customer_id=customer.customer_id,
        requested_amount=payload.requested_amount,
        tenure_months=payload.tenure_months,
        purpose=payload.purpose,
        channel=payload.channel,
        status=m.ApplicationStatus.DRAFT.value,
        policy_version=get_policy_config().policy_id,
    )
    db.add(app)
    db.flush()
    log_audit(db, app.application_id, payload.full_name, "APPLICATION_CREATED", "Draft application created.")
    db.commit()
    return _out(_app_with_relations(db, app.application_id))


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: str, db: Session = Depends(get_db)):
    return _out(_app_with_relations(db, application_id))


@router.patch("/{application_id}", response_model=ApplicationOut)
def patch_application(application_id: str, payload: ApplicationPatch, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    if app.status != m.ApplicationStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Only DRAFT applications can be edited")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    db.commit()
    return _out(_app_with_relations(db, application_id))


@router.post("/{application_id}/submit", response_model=ApplicationOut)
def submit_application(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    try:
        require_transition(app.status, m.ApplicationStatus.SUBMITTED.value)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    app.status = m.ApplicationStatus.SUBMITTED.value
    app.submitted_at = datetime.now(timezone.utc)
    log_audit(db, application_id, app.customer.full_name or "customer", "APPLICATION_SUBMITTED", "Customer submitted application.")
    db.commit()
    return _out(_app_with_relations(db, application_id))


@router.get("/{application_id}/documents", response_model=list[DocumentOut])
def list_documents(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    docs = db.execute(select(m.Document).where(m.Document.application_id == application_id)).scalars().all()
    return docs


@router.post("/{application_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    application_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    app = _app_with_relations(db, application_id)
    file_bytes = await file.read()
    result = process_document(
        application_id,
        document_type,
        file.filename or "document",
        declared_name=app.customer.full_name or "",
        declared_monthly_income=app.customer.monthly_income,
        file_bytes=file_bytes,
        content_type=file.content_type,
    )
    doc = m.Document(
        application_id=application_id,
        document_type=document_type,
        status=result["status"],
        ocr_confidence=result["ocr_confidence"],
        income_mismatch_ratio=result["income_mismatch_ratio"],
        name_match=result["name_match"],
        file_name=file.filename,
        file_url=result["file_url"],
        extracted_fields=result["extracted_fields"],
    )
    db.add(doc)
    if app.status == m.ApplicationStatus.SUBMITTED.value:
        require_transition(app.status, m.ApplicationStatus.DATA_COLLECTION.value)
        app.status = m.ApplicationStatus.DATA_COLLECTION.value
    log_audit(db, application_id, app.customer.full_name or "customer", "DOCUMENT_UPLOADED", f"Uploaded {document_type}.")
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{application_id}/agent/run", response_model=ApplicationOut)
def run_agent_endpoint(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    try:
        run_agent(db, application_id)
        db.commit()
    except AgentRunNotAllowedError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _out(_app_with_relations(db, application_id))


@router.get("/{application_id}/agent/events")
def list_agent_events(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    events = db.execute(
        select(m.AgentEvent).where(m.AgentEvent.application_id == application_id).order_by(m.AgentEvent.step)
    ).scalars().all()
    return events


@router.get("/{application_id}/audit-events")
def list_audit_events(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    events = db.execute(
        select(m.AuditEvent).where(m.AuditEvent.application_id == application_id).order_by(m.AuditEvent.created_at)
    ).scalars().all()
    return events


@router.post("/{application_id}/credit-score", response_model=ModelOutputOut)
def credit_score(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    output = scoring.score_credit(db, application_id)
    db.commit()
    return output


@router.post("/{application_id}/fraud-score", response_model=ModelOutputOut)
def fraud_score(application_id: str, db: Session = Depends(get_db)):
    _app_with_relations(db, application_id)
    ensure_fraud_features(db, application_id)
    output = scoring.score_fraud(db, application_id)
    db.commit()
    return output


@router.post("/{application_id}/policy-evaluate", response_model=PolicyResultOut)
def policy_evaluate(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    policy = get_policy_config()
    subject = build_policy_subject(app.customer, app)
    evaluation = policy.evaluate(subject)
    result = m.PolicyResult(
        application_id=application_id,
        policy_version=evaluation.policy_version,
        overall_pass=evaluation.overall_pass,
        rules=evaluation.to_dict()["rules"],
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@router.get("/{application_id}/offer", response_model=OfferOut)
def get_offer(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    offer = max(app.offers, key=lambda o: o.created_at, default=None)
    if offer is None:
        raise HTTPException(status_code=404, detail="No offer for this application")
    return offer


@router.post("/{application_id}/offer/accept", response_model=ApplicationOut)
def accept_offer(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    offer = max(app.offers, key=lambda o: o.created_at, default=None)
    if offer is None:
        raise HTTPException(status_code=404, detail="No offer to accept")
    try:
        require_transition(app.status, m.ApplicationStatus.AGREEMENT.value)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    offer.status = "ACCEPTED"
    app.status = m.ApplicationStatus.AGREEMENT.value
    db.add(m.Agreement(application_id=application_id, status="PENDING_SIGNATURE"))
    log_audit(db, application_id, app.customer.full_name or "customer", "OFFER_ACCEPTED", "Customer accepted the offer.")
    db.commit()
    return _out(_app_with_relations(db, application_id))


@router.post("/{application_id}/agreement", response_model=ApplicationOut)
def sign_agreement(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    agreement = max(app.agreements, key=lambda a: a.created_at, default=None)
    if agreement is None:
        raise HTTPException(status_code=404, detail="No agreement to sign")
    agreement.status = "SIGNED"
    agreement.signed_at = datetime.now(timezone.utc)
    agreement.document_url = "#"
    log_audit(db, application_id, app.customer.full_name or "customer", "AGREEMENT_SIGNED", "Customer completed e-signature.")
    db.commit()
    return _out(_app_with_relations(db, application_id))


@router.post("/{application_id}/disbursal", response_model=ApplicationOut)
def disburse(application_id: str, db: Session = Depends(get_db)):
    app = _app_with_relations(db, application_id)
    agreement = max(app.agreements, key=lambda a: a.created_at, default=None)
    if agreement is None or agreement.status != "SIGNED":
        raise HTTPException(status_code=409, detail="Agreement must be signed before disbursal")
    try:
        require_transition(app.status, m.ApplicationStatus.MOCK_DISBURSAL.value)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    app.status = m.ApplicationStatus.MOCK_DISBURSAL.value
    log_audit(db, application_id, "system", "MOCK_DISBURSAL", "Funds mock-disbursed to linked account.")
    db.commit()
    return _out(_app_with_relations(db, application_id))
