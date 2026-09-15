"""One-off validation: does our policy engine reproduce policy_results.csv?
Not part of the app -- a correctness check before trusting the engine to
backfill full rule-level PolicyResult rows during data load."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.policy.engine import get_policy_config  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


def load_csv(name: str) -> list[dict]:
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


def main():
    customers = {c["customer_id"]: c for c in load_csv("customers.csv")}
    applications = load_csv("applications.csv")
    expected = {r["application_id"]: r for r in load_csv("policy_results.csv")}

    policy = get_policy_config()

    mismatches = []
    for app in applications:
        cust = customers[app["customer_id"]]
        subject = {
            "age": int(cust["age"]),
            "monthly_income": float(cust["monthly_income"]),
            "bureau_score": int(cust["bureau_score"]),
            "foir": float(cust["foir"]),
            "employment_tenure_months": int(cust["employment_tenure_months"]),
            "requested_amount": float(app["requested_amount"]),
        }
        result = policy.evaluate(subject)
        exp = expected[app["application_id"]]
        exp_pass = exp["policy_status"] == "ELIGIBLE"
        exp_failed = set(exp["failed_rules"].split("|")) if exp["failed_rules"] else set()
        got_failed = set(result.failed_rule_codes)

        if result.overall_pass != exp_pass or got_failed != exp_failed:
            mismatches.append(
                {
                    "application_id": app["application_id"],
                    "expected_pass": exp_pass,
                    "got_pass": result.overall_pass,
                    "expected_failed": exp_failed,
                    "got_failed": got_failed,
                }
            )

    print(f"Checked {len(applications)} applications")
    print(f"Mismatches: {len(mismatches)}")
    for m in mismatches[:20]:
        print(m)


if __name__ == "__main__":
    main()
