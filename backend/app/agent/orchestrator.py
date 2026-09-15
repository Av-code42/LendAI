"""
The agent orchestrator. This is a DETERMINISTIC stand-in for a real
LLM-driven agent: it calls the same tools, through the same
schema/permission/timeout gate (app/agent/dispatcher.py), in the same
order an LLM following the PRD's tool contract would -- but the
tool-selection logic here is a fixed script, not a model making
judgement calls. Swapping this module for a real LLM loop (e.g. Claude
deciding which tool to call next, given the same tool contract and the
same dispatcher) is the natural next milestone; it changes nothing about
the guardrails, because those live in the dispatcher/state
machine/router, not here.

Runnable entry point: run_agent(session, application_id).
"""

from __future__ import annotations

from sqlalchemy import select

from app.agent.dispatcher import AgentContext, AgentStepLimitExceeded
from app.core.audit import log_audit
from app.core.state_machine import can_transition, require_transition
from app.db import models as m
from app.routing.evidence import check_evidence
from app.routing.router import RoutingSignals, route

RUNNABLE_STATUSES = {
    m.ApplicationStatus.SUBMITTED.value,
    m.ApplicationStatus.DATA_COLLECTION.value,
    m.ApplicationStatus.WAITING_FOR_DOCUMENT.value,
}

_REQUEST_DOC_REASONS = {
    "missing": "Required document not yet uploaded.",
    "low_confidence": "Uploaded document's OCR confidence is below the required threshold; please re-upload a clearer copy.",
}


class AgentRunNotAllowedError(Exception):
    pass


def _recommendation_summary(status: str, reason_codes: list[str]) -> str:
    if status == m.ApplicationStatus.AUTO_APPROVED.value:
        return "All policy rules pass and credit/fraud risk are both low. Recommending auto-approval."
    if status == m.ApplicationStatus.DECLINED.value:
        return f"Policy evaluation failed ({', '.join(reason_codes)}). Routing to decline."
    if status == m.ApplicationStatus.HUMAN_REVIEW.value:
        return f"Routing to mandatory human review ({', '.join(reason_codes)})."
    return f"Requesting additional evidence ({', '.join(reason_codes)})."


def run_agent(session, application_id: str) -> m.Application:
    app = session.get(m.Application, application_id)
    if app is None:
        raise ValueError(f"Application {application_id} not found")
    if app.status not in RUNNABLE_STATUSES:
        raise AgentRunNotAllowedError(
            f"Agent cannot run from status {app.status} (must be one of {sorted(RUNNABLE_STATUSES)})"
        )

    ctx = AgentContext(session, application_id)

    try:
        ctx.call_tool("get_customer_profile", application_id=application_id)

        if app.status == m.ApplicationStatus.SUBMITTED.value:
            require_transition(app.status, m.ApplicationStatus.DATA_COLLECTION.value)
            app.status = m.ApplicationStatus.DATA_COLLECTION.value

        documents = session.execute(
            select(m.Document).where(m.Document.application_id == application_id)
        ).scalars().all()
        evidence = check_evidence(documents)

        if not evidence.ok:
            for doc_type in evidence.missing_document_types:
                ctx.call_tool(
                    "request_document",
                    application_id=application_id,
                    document_type=doc_type,
                    reason=_REQUEST_DOC_REASONS["missing"],
                )
            for doc_type in evidence.low_confidence_document_types:
                ctx.call_tool(
                    "request_document",
                    application_id=application_id,
                    document_type=doc_type,
                    reason=_REQUEST_DOC_REASONS["low_confidence"],
                )
            ctx.log_evidence_analysis(
                f"Evidence incomplete -- missing={evidence.missing_document_types}, "
                f"low_confidence={evidence.low_confidence_document_types}. "
                "Cannot proceed to verification until resolved."
            )
            log_audit(session, application_id, "agent", "AGENT_RUN_PAUSED", f"Waiting for document(s): status={app.status}")
            session.flush()
            return app

        require_transition(app.status, m.ApplicationStatus.VERIFICATION.value)
        app.status = m.ApplicationStatus.VERIFICATION.value
        ctx.log_evidence_analysis("All required documents present and above the OCR confidence threshold.")

        require_transition(app.status, m.ApplicationStatus.RISK_ASSESSMENT.value)
        app.status = m.ApplicationStatus.RISK_ASSESSMENT.value

        credit_result = ctx.call_tool("run_credit_model", application_id=application_id)
        fraud_result = ctx.call_tool("run_fraud_check", application_id=application_id)

        require_transition(app.status, m.ApplicationStatus.POLICY_EVALUATION.value)
        app.status = m.ApplicationStatus.POLICY_EVALUATION.value

        policy_result = ctx.call_tool(
            "evaluate_policy", application_id=application_id, policy_version=app.policy_version
        )

        signals = RoutingSignals(
            fraud_risk=fraud_result["risk_level"],
            credit_risk=credit_result["risk_level"],
            policy_pass=policy_result["overall_pass"],
            policy_failed_reason_codes=[r["reason_code"] for r in policy_result["rules"] if not r["pass"]],
            evidence=evidence,
        )
        decision = route(signals)
        require_transition(app.status, decision.status)

        summary = _recommendation_summary(decision.status, decision.reason_codes)

        if decision.status == m.ApplicationStatus.HUMAN_REVIEW.value:
            app.status = decision.status
            ctx.call_tool(
                "create_human_review", application_id=application_id, reason="|".join(decision.reason_codes)
            )
            ctx.log_review_case_created(f"Created human review case: {', '.join(decision.reason_codes)}.")
            ctx.log_recommendation(summary, decision.reason_codes, "HUMAN_REVIEW")

        elif decision.status == m.ApplicationStatus.DECLINED.value:
            app.status = decision.status
            ctx.log_recommendation(summary, decision.reason_codes, "DECLINE")

        elif decision.status == m.ApplicationStatus.AUTO_APPROVED.value:
            app.status = decision.status
            ctx.log_recommendation(summary, decision.reason_codes, "AUTO_APPROVE")
            ctx.call_tool(
                "generate_offer",
                application_id=application_id,
                amount=app.requested_amount,
                tenure_months=app.tenure_months,
            )

        elif decision.status == m.ApplicationStatus.WAITING_FOR_DOCUMENT.value:
            app.status = decision.status
            ctx.log_recommendation(summary, decision.reason_codes, "REQUEST_DOCUMENT")

        log_audit(session, application_id, "agent", "AGENT_RUN_COMPLETE", f"Routed to {app.status}.")

    except AgentStepLimitExceeded:
        # Fail-safe escalation per the PRD guardrails: never leave an
        # application stuck mid-pipeline because the agent ran away.
        if can_transition(app.status, m.ApplicationStatus.HUMAN_REVIEW.value):
            app.status = m.ApplicationStatus.HUMAN_REVIEW.value
        log_audit(
            session,
            application_id,
            "system",
            "AGENT_STEP_LIMIT_ESCALATION",
            "Agent exceeded its per-run step limit; escalated to human review as a fail-safe.",
        )
        raise

    session.flush()
    return app
