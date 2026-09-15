"""One-off validation: does our router (using the HISTORICAL risk bands
already loaded, not our own newly-trained model) reproduce
decision_routing.csv for all 10,000 historical applications?"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.db.base import SessionLocal  # noqa: E402
from app.db import models as m  # noqa: E402
from app.routing.evidence import check_evidence  # noqa: E402
from app.routing.router import RoutingSignals, route  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


def load_csv(name: str) -> list[dict]:
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


STATUS_TO_ROUTING_DECISION = {
    "AUTO_APPROVED": "AUTO_APPROVE",
    "DECLINED": "DECLINE",
    "HUMAN_REVIEW": "HUMAN_REVIEW",
    "WAITING_FOR_DOCUMENT": "HUMAN_REVIEW",  # dataset folds this into HUMAN_REVIEW
}


def main():
    expected = {r["application_id"]: r for r in load_csv("decision_routing.csv")}
    session = SessionLocal()
    mismatches = []
    try:
        apps = session.execute(select(m.Application)).scalars().all()
        for app in apps:
            docs = session.execute(
                select(m.Document).where(m.Document.application_id == app.application_id)
            ).scalars().all()
            evidence = check_evidence(docs)

            policy_result = session.execute(
                select(m.PolicyResult).where(m.PolicyResult.application_id == app.application_id)
            ).scalars().first()

            credit_mo = session.execute(
                select(m.ModelOutput)
                .where(m.ModelOutput.application_id == app.application_id, m.ModelOutput.model_type == "CREDIT")
                .order_by(m.ModelOutput.scored_at.desc())
            ).scalars().first()
            fraud_mo = session.execute(
                select(m.ModelOutput)
                .where(m.ModelOutput.application_id == app.application_id, m.ModelOutput.model_type == "FRAUD")
                .order_by(m.ModelOutput.scored_at.desc())
            ).scalars().first()

            signals = RoutingSignals(
                fraud_risk=fraud_mo.risk_level,
                credit_risk=credit_mo.risk_level,
                policy_pass=policy_result.overall_pass,
                policy_failed_reason_codes=[r["reason_code"] for r in policy_result.rules if not r["pass"]],
                evidence=evidence,
            )
            decision = route(signals)
            got = STATUS_TO_ROUTING_DECISION[decision.status]
            exp = expected[app.application_id]["routing_decision"]

            if got != exp:
                mismatches.append(
                    {
                        "application_id": app.application_id,
                        "expected": exp,
                        "got": got,
                        "reason_codes": decision.reason_codes,
                        "expected_reason": expected[app.application_id]["routing_reason"],
                    }
                )
    finally:
        session.close()

    print(f"Checked {len(apps)} applications")
    print(f"Mismatches: {len(mismatches)}")
    for mm in mismatches[:30]:
        print(mm)


if __name__ == "__main__":
    main()
