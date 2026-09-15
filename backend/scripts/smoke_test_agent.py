"""Manual smoke test for the agent orchestrator + dispatcher + router,
end to end, against a fresh (uncommitted) application. Rolls back at the
end so it never pollutes real data."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.dispatcher import ProhibitedToolError  # noqa: E402
from app.agent.orchestrator import run_agent  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.db import models as m  # noqa: E402

session = SessionLocal()
try:
    # A real low-risk historical customer, but a brand new application.
    customer = session.query(m.Customer).filter(m.Customer.bureau_score >= 750).first()
    app = m.Application(
        application_id="APPTEST0001",
        customer_id=customer.customer_id,
        requested_amount=300000,
        tenure_months=24,
        purpose="EDUCATION",
        channel="WEB",
        status=m.ApplicationStatus.SUBMITTED.value,
        policy_version="PL_2026_V1",
    )
    session.add(app)
    session.flush()

    print("=== Run 1: no documents uploaded yet ===")
    run_agent(session, app.application_id)
    print("status after run 1:", app.status)
    assert app.status == m.ApplicationStatus.WAITING_FOR_DOCUMENT.value

    print("\n=== Uploading documents, run 2 ===")
    for doc_type in ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]:
        session.add(
            m.Document(
                application_id=app.application_id,
                document_type=doc_type,
                status="UPLOADED",
                ocr_confidence=0.95,
                income_mismatch_ratio=0.05,
                name_match=True,
            )
        )
    session.flush()
    run_agent(session, app.application_id)
    print("status after run 2:", app.status)

    events = (
        session.query(m.AgentEvent)
        .filter(m.AgentEvent.application_id == app.application_id)
        .order_by(m.AgentEvent.step)
        .all()
    )
    print(f"\n=== {len(events)} agent events ===")
    for e in events:
        print(f"  step={e.step} type={e.type} tool={e.tool_name} :: {e.detail[:100]}")

    print("\n=== Testing a prohibited tool call is blocked ===")
    from app.agent.dispatcher import AgentContext

    ctx = AgentContext(session, app.application_id)
    try:
        ctx.call_tool("override_policy_decision", application_id=app.application_id)
        print("FAIL: prohibited tool call was NOT blocked")
    except ProhibitedToolError as e:
        print("OK: blocked as expected ->", e)

finally:
    session.rollback()
    session.close()
    print("\n(rolled back -- no data persisted)")
