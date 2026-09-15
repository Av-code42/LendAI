"""
The PRD's golden + adversarial test cases, run against the real HTTP API
(so state machine, dispatcher, router, and audit trail are all genuinely
exercised end to end). Credit/fraud SCORING is monkeypatched to a
controlled value for each case -- the ML models themselves are already
evaluated separately in app/ml/train.py's held-out test split; these
tests are about the deterministic decision plumbing around them, which is
the part the PRD actually specifies test cases for.
"""

from __future__ import annotations

import app.ml.scoring as scoring_module
from app.db import models as m

APPLICANT = {
    "full_name": "Golden Case",
    "email": "golden@example.com",
    "phone": "+91 90000 00001",
    "monthly_income": 90000,
    "age": 32,
    "employment_tenure_months": 36,
    "relationship_months": 48,
    "bureau_score": 760,
    "requested_amount": 300000,
    "tenure_months": 24,
    "purpose": "HOME_RENOVATION",
}


def _mock_scores(monkeypatch, credit_risk="LOW", fraud_risk="LOW"):
    def fake_credit(session, application_id):
        out = m.ModelOutput(
            application_id=application_id,
            model_type="CREDIT",
            model_name="TEST_STUB",
            model_version="test-v0",
            score={"LOW": 0.05, "MEDIUM": 0.15, "HIGH": 0.4}[credit_risk],
            risk_level=credit_risk,
        )
        session.add(out)
        session.flush()
        return out

    def fake_fraud(session, application_id):
        out = m.ModelOutput(
            application_id=application_id,
            model_type="FRAUD",
            model_name="TEST_STUB",
            model_version="test-v0",
            score={"LOW": 0.02, "MEDIUM": 0.3, "HIGH": 0.8}[fraud_risk],
            risk_level=fraud_risk,
        )
        session.add(out)
        session.flush()
        return out

    monkeypatch.setattr(scoring_module, "score_credit", fake_credit)
    monkeypatch.setattr(scoring_module, "score_fraud", fake_fraud)


def _create_and_submit(client, **overrides) -> str:
    payload = {**APPLICANT, **overrides}
    resp = client.post("/applications", json=payload)
    assert resp.status_code == 201, resp.text
    app_id = resp.json()["application_id"]
    resp = client.post(f"/applications/{app_id}/submit")
    assert resp.status_code == 200
    return app_id


# --- 1. clean low-risk -> auto approve --------------------------------------


def test_golden_1_clean_low_risk_auto_approves(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "LOW")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(
            m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97)
        )
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "OFFER"  # AUTO_APPROVED immediately generates an offer
    assert data["offer"] is not None
    assert data["offer"]["approved_amount"] == APPLICANT["requested_amount"]


# --- 2. high fraud -> human review -------------------------------------------


def test_golden_2_high_fraud_routes_to_human_review(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "HIGH")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HUMAN_REVIEW"

    reviews = client.get("/reviews").json()
    case = next(r for r in reviews if r["application_id"] == app_id)
    assert case["review_reason"] == "HIGH_FRAUD_RISK"


# --- 3. medium fraud -> human review ------------------------------------------


def test_golden_3_medium_fraud_routes_to_human_review(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "MEDIUM")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.json()["status"] == "HUMAN_REVIEW"


# --- 4. policy failure -> decline --------------------------------------------


def test_golden_4_policy_failure_declines(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "LOW")
    # bureau_score below the 700 floor -> policy fails regardless of risk.
    app_id = _create_and_submit(client, bureau_score=650)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    data = resp.json()
    assert data["status"] == "DECLINED"
    assert data["policy_result"]["overall_pass"] is False
    failed_codes = [r["reason_code"] for r in data["policy_result"]["rules"] if not r["pass"]]
    assert "POLICY_BUREAU_SCORE_FAIL" in failed_codes


# --- 5. high credit risk -> human review --------------------------------------


def test_golden_5_high_credit_risk_routes_to_human_review(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "HIGH", "LOW")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.json()["status"] == "HUMAN_REVIEW"


# --- 6. missing document -> request document ---------------------------------


def test_golden_6_missing_document_requests_upload(client, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "LOW")
    app_id = _create_and_submit(client)
    # No documents uploaded at all.
    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.json()["status"] == "WAITING_FOR_DOCUMENT"

    events = client.get(f"/applications/{app_id}/agent/events").json()
    assert any(e["type"] == "TOOL_CALL" and e["tool_name"] == "request_document" for e in events)


# --- 7. low OCR confidence -> review/document request -------------------------


def test_golden_7_low_ocr_confidence_requests_upload(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "LOW")
    app_id = _create_and_submit(client)
    db_session.add(m.Document(application_id=app_id, document_type="PAN", status="UPLOADED", ocr_confidence=0.97))
    db_session.add(m.Document(application_id=app_id, document_type="SALARY_SLIP", status="UPLOADED", ocr_confidence=0.40))
    db_session.add(m.Document(application_id=app_id, document_type="BANK_STATEMENT", status="UPLOADED", ocr_confidence=0.95))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.json()["status"] == "WAITING_FOR_DOCUMENT"

    events = client.get(f"/applications/{app_id}/agent/events").json()
    detail_blob = " ".join(e["detail"] for e in events)
    assert "SALARY_SLIP" in detail_blob


# --- 8. prohibited agent action -> blocked ------------------------------------


def test_golden_8_prohibited_tool_call_is_blocked(client, db_session):
    from app.agent.dispatcher import AgentContext, ProhibitedToolError

    app_id = _create_and_submit(client)
    ctx = AgentContext(db_session, app_id)
    try:
        ctx.call_tool("override_policy_decision", application_id=app_id)
        assert False, "prohibited tool call should have raised"
    except ProhibitedToolError:
        pass

    events = client.get(f"/applications/{app_id}/agent/events").json()
    assert any(e["type"] == "BLOCKED_ACTION" for e in events)

    # And the application's state must be completely untouched.
    app_data = client.get(f"/applications/{app_id}").json()
    assert app_data["status"] == "SUBMITTED"


# --- adversarial: duplicate applications --------------------------------------


def test_adversarial_duplicate_applications_get_distinct_ids(client):
    id_a = _create_and_submit(client)
    id_b = _create_and_submit(client)  # identical payload
    assert id_a != id_b


# --- adversarial: conflicting/invalid state transitions -----------------------


def test_adversarial_cannot_submit_twice(client):
    app_id = _create_and_submit(client)
    resp = client.post(f"/applications/{app_id}/submit")
    assert resp.status_code == 409


def test_adversarial_cannot_edit_after_submit(client):
    app_id = _create_and_submit(client)
    resp = client.patch(f"/applications/{app_id}", json={"purpose": "TRAVEL"})
    assert resp.status_code == 409


def test_adversarial_double_review_decision_rejected(client, db_session, monkeypatch):
    _mock_scores(monkeypatch, "LOW", "HIGH")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()
    client.post(f"/applications/{app_id}/agent/run")

    review_id = next(r["review_id"] for r in client.get("/reviews").json() if r["application_id"] == app_id)
    decision = {"user_id": "u1", "user_name": "Test UW", "action": "REJECT", "reason_code": "RISK_TOO_HIGH", "comment": "no"}
    first = client.post(f"/reviews/{review_id}/decision", json=decision)
    assert first.status_code == 200
    second = client.post(f"/reviews/{review_id}/decision", json=decision)
    assert second.status_code == 409


# --- adversarial: agent loop / step-limit guardrail ----------------------------


def test_adversarial_agent_step_limit_escalates_to_human_review(client, db_session, monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "agent_max_steps", 1)
    _mock_scores(monkeypatch, "LOW", "LOW")
    app_id = _create_and_submit(client)
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        db_session.add(m.Document(application_id=app_id, document_type=doc_type, status="UPLOADED", ocr_confidence=0.97))
    db_session.commit()

    resp = client.post(f"/applications/{app_id}/agent/run")
    assert resp.status_code == 409  # AgentStepLimitExceeded

    events = client.get(f"/applications/{app_id}/agent/events").json()
    assert any(e["type"] == "BLOCKED_ACTION" for e in events)


# --- adversarial: tool timeout --------------------------------------------------


def test_adversarial_tool_timeout_is_enforced(db_session, monkeypatch):
    import time

    import app.core.config as config_module
    from app.agent.dispatcher import AgentContext, ToolTimeoutError
    import app.agent.tools as tools_module

    monkeypatch.setattr(config_module.settings, "tool_timeout_seconds", 0.2)

    def slow_get_customer_profile(session, application_id):
        time.sleep(1)
        return {}

    monkeypatch.setitem(tools_module.TOOL_FUNCTIONS, "get_customer_profile", slow_get_customer_profile)

    # AgentEvent.application_id is a real foreign key, so a minimal
    # customer + application row must exist even though the (monkeypatched)
    # tool function itself never touches the DB.
    customer = m.Customer(
        customer_id="CUSTIMEOUTTEST",
        age=30,
        monthly_income=90000,
        employment_tenure_months=24,
        relationship_months=24,
        bureau_score=750,
        active_loans=0,
        existing_monthly_emi=0,
        foir=0.1,
    )
    db_session.add(customer)
    db_session.add(
        m.Application(
            application_id="APPTIMEOUTTEST",
            customer_id="CUSTIMEOUTTEST",
            requested_amount=100000,
            tenure_months=12,
            purpose="OTHER",
            status="SUBMITTED",
            policy_version="PL_2026_V1",
        )
    )
    db_session.flush()

    ctx = AgentContext(db_session, "APPTIMEOUTTEST")
    try:
        ctx.call_tool("get_customer_profile", application_id="APPTIMEOUTTEST")
        assert False, "expected a timeout"
    except ToolTimeoutError:
        pass
