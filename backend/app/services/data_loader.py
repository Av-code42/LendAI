"""
Loads the 9 bundle files (customers, applications, transactions,
documents, fraud_features, decision_routing, model_outputs,
policy_results, human_review_cases) into Postgres.

Lives in app/ (not scripts/) specifically so it ships with the deployed
Vercel function -- app/api/admin.py's bootstrap endpoint calls
`load_all()` directly, since a serverless deployment has no shell to run
scripts/load_data.py from. scripts/load_data.py is now a thin CLI wrapper
around this module for local/Docker use.

Design notes:
- Historical applications are loaded already at their terminal routing
  status (AUTO_APPROVED / DECLINED / HUMAN_REVIEW) as recorded in
  decision_routing.csv -- they represent completed historical decisions,
  not live in-flight applications. New applications created through the
  live API start at DRAFT and move through the real state machine.
- policy_results rows are NOT copied verbatim from policy_results.csv.
  They are recomputed with our own policy engine (validated to match the
  CSV 1:1 across all 10,000 rows by scripts/validate_policy.py) so we get
  full rule-level detail (actual value + threshold per rule), which the
  flat CSV (just policy_status + failed_rules) doesn't carry.
- model_outputs rows loaded from model_outputs.csv are tagged
  model_name="HISTORICAL" to distinguish them honestly from scores our
  own trained models produce later (model_name will be
  LOGISTIC_REGRESSION / RANDOM_FOREST / XGBOOST) -- we don't actually
  know what algorithm generated the dataset's baseline scores.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.engine import Engine

from app.core.config import DATA_DIR
from app.db import models as m
from app.policy.engine import get_policy_config

CHUNK = 1000

ROUTING_TO_STATUS = {
    "AUTO_APPROVE": m.ApplicationStatus.AUTO_APPROVED.value,
    "DECLINE": m.ApplicationStatus.DECLINED.value,
    "HUMAN_REVIEW": m.ApplicationStatus.HUMAN_REVIEW.value,
}


def _load_csv(data_dir: Path, name: str) -> list[dict]:
    with open(data_dir / name, newline="") as f:
        return list(csv.DictReader(f))


def _to_bool(v: str) -> bool:
    return v.strip().lower() == "true"


def _parse_dt(v: str) -> datetime:
    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")


def _chunked(rows: list[dict], size: int = CHUNK):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _bulk_insert(conn, table, rows: list[dict]):
    if not rows:
        return
    for batch in _chunked(rows):
        conn.execute(table.insert(), batch)


def load_all(engine: Engine, reset: bool, data_dir: Path = DATA_DIR, log=print) -> dict:
    customers_csv = _load_csv(data_dir, "customers.csv")
    applications_csv = _load_csv(data_dir, "applications.csv")
    transactions_csv = _load_csv(data_dir, "transactions.csv")
    documents_csv = _load_csv(data_dir, "documents.csv")
    fraud_features_csv = _load_csv(data_dir, "fraud_features.csv")
    decision_routing_csv = {r["application_id"]: r for r in _load_csv(data_dir, "decision_routing.csv")}
    model_outputs_csv = _load_csv(data_dir, "model_outputs.csv")
    human_review_csv = _load_csv(data_dir, "human_review_cases.csv")

    policy = get_policy_config()
    counts: dict[str, int] = {}

    with engine.begin() as conn:
        if reset:
            log("Resetting tables...")
            for table in reversed(m.Base.metadata.sorted_tables):
                conn.execute(delete(table))

        # --- customers ---
        customer_rows = [
            dict(
                customer_id=c["customer_id"],
                age=int(c["age"]),
                monthly_income=float(c["monthly_income"]),
                employment_tenure_months=int(c["employment_tenure_months"]),
                relationship_months=int(c["relationship_months"]),
                bureau_score=int(c["bureau_score"]),
                active_loans=int(c["active_loans"]),
                existing_monthly_emi=float(c["existing_monthly_emi"]),
                foir=float(c["foir"]),
                employment_type=c["employment_type"],
            )
            for c in customers_csv
        ]
        _bulk_insert(conn, m.Customer.__table__, customer_rows)
        counts["customers"] = len(customer_rows)
        log(f"Loaded {len(customer_rows)} customers")

        # --- transactions ---
        txn_rows = [
            dict(
                customer_id=t["customer_id"],
                avg_monthly_credits=float(t["avg_monthly_credits"]),
                salary_consistency=float(t["salary_consistency"]),
                cash_withdrawal_ratio=float(t["cash_withdrawal_ratio"]),
                monthly_transaction_count=int(t["monthly_transaction_count"]),
            )
            for t in transactions_csv
        ]
        _bulk_insert(conn, m.Transaction.__table__, txn_rows)
        counts["transactions"] = len(txn_rows)
        log(f"Loaded {len(txn_rows)} transactions")

        # --- applications (+ policy evaluation backfill) ---
        customers_by_id = {c["customer_id"]: c for c in customers_csv}
        model_outputs_by_app = {r["application_id"]: r for r in model_outputs_csv}

        application_rows = []
        policy_result_rows = []
        for a in applications_csv:
            cust = customers_by_id[a["customer_id"]]
            submitted_at = _parse_dt(a["submitted_at"])
            routing = decision_routing_csv[a["application_id"]]
            mo = model_outputs_by_app.get(a["application_id"])

            application_rows.append(
                dict(
                    application_id=a["application_id"],
                    customer_id=a["customer_id"],
                    requested_amount=float(a["requested_amount"]),
                    tenure_months=int(a["tenure_months"]),
                    purpose=a["purpose"],
                    channel=a["channel"],
                    status=ROUTING_TO_STATUS[routing["routing_decision"]],
                    policy_version=policy.policy_id,
                    actual_default_label=int(mo["actual_default_label"]) if mo else None,
                    actual_fraud_label=int(mo["actual_fraud_label"]) if mo else None,
                    submitted_at=submitted_at,
                    created_at=submitted_at,
                    updated_at=submitted_at,
                )
            )

            subject = {
                "age": int(cust["age"]),
                "monthly_income": float(cust["monthly_income"]),
                "bureau_score": int(cust["bureau_score"]),
                "foir": float(cust["foir"]),
                "employment_tenure_months": int(cust["employment_tenure_months"]),
                "requested_amount": float(a["requested_amount"]),
            }
            evaluation = policy.evaluate(subject)
            policy_result_rows.append(
                dict(
                    application_id=a["application_id"],
                    policy_version=evaluation.policy_version,
                    overall_pass=evaluation.overall_pass,
                    rules=evaluation.to_dict()["rules"],
                    evaluated_at=submitted_at,
                )
            )

        _bulk_insert(conn, m.Application.__table__, application_rows)
        counts["applications"] = len(application_rows)
        log(f"Loaded {len(application_rows)} applications")
        _bulk_insert(conn, m.PolicyResult.__table__, policy_result_rows)
        counts["policy_results"] = len(policy_result_rows)
        log(f"Backfilled {len(policy_result_rows)} policy results (recomputed, not copied)")

        # --- documents ---
        doc_rows = [
            dict(
                application_id=d["application_id"],
                document_type=d["document_type"],
                status=d["status"],
                ocr_confidence=float(d["ocr_confidence"]) if d["ocr_confidence"] else None,
                income_mismatch_ratio=float(d["income_mismatch_ratio"]) if d["income_mismatch_ratio"] else None,
                name_match=_to_bool(d["name_match"]) if d["name_match"] != "" else None,
            )
            for d in documents_csv
        ]
        _bulk_insert(conn, m.Document.__table__, doc_rows)
        counts["documents"] = len(doc_rows)
        log(f"Loaded {len(doc_rows)} documents")

        # --- fraud features ---
        ff_rows = [
            dict(
                application_id=f["application_id"],
                device_reuse_count_30d=int(f["device_reuse_count_30d"]),
                applications_last_7d=int(f["applications_last_7d"]),
                location_mismatch=int(f["location_mismatch"]),
                bank_account_age_months=int(f["bank_account_age_months"]),
                document_anomaly_score=float(f["document_anomaly_score"]),
                income_mismatch_score=float(f["income_mismatch_score"]),
                fraud_label=int(f["fraud_label"]),
            )
            for f in fraud_features_csv
        ]
        _bulk_insert(conn, m.FraudFeatures.__table__, ff_rows)
        counts["fraud_features"] = len(ff_rows)
        log(f"Loaded {len(ff_rows)} fraud feature rows")

        # --- historical model outputs (tagged HISTORICAL, see module docstring) ---
        mo_rows = []
        submitted_at_by_app = {a["application_id"]: _parse_dt(a["submitted_at"]) for a in applications_csv}
        for r in model_outputs_csv:
            ts = submitted_at_by_app[r["application_id"]]
            mo_rows.append(
                dict(
                    application_id=r["application_id"],
                    model_type=m.ModelType.CREDIT.value,
                    model_name="HISTORICAL",
                    model_version=r["credit_model_version"],
                    score=float(r["credit_pd"]),
                    risk_level=r["credit_risk_band"],
                    scored_at=ts,
                )
            )
            mo_rows.append(
                dict(
                    application_id=r["application_id"],
                    model_type=m.ModelType.FRAUD.value,
                    model_name="HISTORICAL",
                    model_version=r["fraud_model_version"],
                    score=float(r["fraud_probability"]),
                    risk_level=r["fraud_risk_band"],
                    scored_at=ts,
                )
            )
        _bulk_insert(conn, m.ModelOutput.__table__, mo_rows)
        counts["model_outputs"] = len(mo_rows)
        log(f"Loaded {len(mo_rows)} historical model output rows")

        # --- human review cases ---
        review_rows = [
            dict(
                review_id=r["review_id"],
                application_id=r["application_id"],
                review_reason=r["review_reason"],
                agent_recommendation=r["agent_recommendation"] or None,
                status=m.ReviewStatus.OPEN.value if r["status"] == "PENDING" else m.ReviewStatus.CLOSED.value,
                decided_by_user_id=None,
                decided_by_user_name=None,
                decision_action=r["underwriter_decision"] or None,
                decision_reason_code=r["decision_reason"] or None,
                decision_comment=None,
                decided_at=None,
                created_at=submitted_at_by_app[r["application_id"]],
            )
            for r in human_review_csv
        ]
        _bulk_insert(conn, m.HumanReviewCase.__table__, review_rows)
        counts["human_review_cases"] = len(review_rows)
        log(f"Loaded {len(review_rows)} human review cases")

        # --- audit trail for bulk-imported historical applications ---
        audit_rows = []
        for a in applications_csv:
            ts = submitted_at_by_app[a["application_id"]]
            routing = decision_routing_csv[a["application_id"]]
            audit_rows.append(
                dict(
                    application_id=a["application_id"],
                    actor="system",
                    action="APPLICATION_IMPORTED",
                    detail="Historical application imported from dataset bundle.",
                    created_at=ts,
                )
            )
            audit_rows.append(
                dict(
                    application_id=a["application_id"],
                    actor="system",
                    action="ROUTING_DECISION",
                    detail=f"Routed to {routing['routing_decision']} ({routing['routing_reason']}).",
                    created_at=ts,
                )
            )
        _bulk_insert(conn, m.AuditEvent.__table__, audit_rows)
        counts["audit_events"] = len(audit_rows)
        log(f"Loaded {len(audit_rows)} audit events")

    log("Done.")
    return counts
