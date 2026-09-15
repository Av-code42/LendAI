"""
Deterministic policy engine for policy PL_2026_V1
(config/personal_loan_policy_v1.json).

This is intentionally the *only* place credit-policy eligibility is
decided. The agent/LLM layer may call `evaluate_policy` as a tool, but it
never re-implements or approximates this logic itself (PRD core rule).
"""

from __future__ import annotations

import ast
import json
import operator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

# --- restricted arithmetic evaluator for rules that use an "expression"
# instead of a static "value" (e.g. LOAN_TO_INCOME: monthly_income * 8).
# Only names, numeric literals, and +-*/ are allowed -- no calls, no
# attribute access, nothing that could execute arbitrary code.
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _safe_eval_expression(expr: str, subject: dict[str, Any]) -> float:
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in subject:
                raise ValueError(f"Unknown field '{node.id}' in policy expression")
            return subject[node.id]
        raise ValueError(f"Disallowed expression syntax: {ast.dump(node)}")

    return _eval(tree)


RULE_LABELS: dict[str, str] = {
    "AGE": "Applicant age within policy range",
    "MIN_INCOME": "Minimum monthly income",
    "BUREAU_SCORE": "Minimum bureau score",
    "FOIR": "Maximum fixed obligation to income ratio",
    "EMPLOYMENT_TENURE": "Minimum employment tenure",
    "LOAN_TO_INCOME": "Requested amount within income multiple",
}


@dataclass
class RuleResult:
    rule_code: str
    label: str
    passed: bool
    actual_value: Any
    threshold: Any
    reason_code: str | None = None

    def to_dict(self) -> dict:
        return {
            "rule_code": self.rule_code,
            "label": self.label,
            "pass": self.passed,
            "actual_value": self.actual_value,
            "threshold": self.threshold,
            "reason_code": self.reason_code,
        }


@dataclass
class PolicyEvaluation:
    policy_version: str
    overall_pass: bool
    rules: list[RuleResult] = field(default_factory=list)

    @property
    def failed_rule_codes(self) -> list[str]:
        return [r.rule_code for r in self.rules if not r.passed]

    def to_dict(self) -> dict:
        return {
            "policy_version": self.policy_version,
            "overall_pass": self.overall_pass,
            "rules": [r.to_dict() for r in self.rules],
        }


class PolicyConfig:
    def __init__(self, raw: dict):
        self.policy_id: str = raw["policy_id"]
        self.product: str = raw["product"]
        self.version: str = raw["version"]
        self.rules: list[dict] = raw["rules"]
        # e.g. {"HIGH": "HUMAN_REVIEW", "MEDIUM": "HUMAN_REVIEW"}
        self.fraud_override: dict[str, str] = raw.get("fraud_override", {})

    def evaluate(self, subject: dict[str, Any]) -> PolicyEvaluation:
        results: list[RuleResult] = []
        for rule in self.rules:
            results.append(self._evaluate_rule(rule, subject))
        return PolicyEvaluation(
            policy_version=self.policy_id,
            overall_pass=all(r.passed for r in results),
            rules=results,
        )

    def _evaluate_rule(self, rule: dict, subject: dict[str, Any]) -> RuleResult:
        rule_id = rule["id"]
        field_name = rule["field"]
        op = rule["operator"]
        actual = subject.get(field_name)
        label = RULE_LABELS.get(rule_id, rule_id)

        if op == "BETWEEN":
            low, high = rule["value"]
            passed = actual is not None and low <= actual <= high
            threshold = f"{low}-{high}"
        elif op in (">=", "<=", ">", "<", "=="):
            if "expression" in rule:
                threshold = _safe_eval_expression(rule["expression"], subject)
            else:
                threshold = rule["value"]
            comparators = {
                ">=": operator.ge,
                "<=": operator.le,
                ">": operator.gt,
                "<": operator.lt,
                "==": operator.eq,
            }
            passed = actual is not None and comparators[op](actual, threshold)
        else:
            raise ValueError(f"Unsupported policy operator: {op}")

        return RuleResult(
            rule_code=rule_id,
            label=label,
            passed=bool(passed),
            actual_value=actual,
            threshold=threshold,
            reason_code=None if passed else f"POLICY_{rule_id}_FAIL",
        )


@lru_cache(maxsize=1)
def get_policy_config(path: Path | None = None) -> PolicyConfig:
    path = path or settings.policy_config_path
    with open(path) as f:
        raw = json.load(f)
    return PolicyConfig(raw)


def build_policy_subject(customer: Any, application: Any) -> dict[str, Any]:
    """Build the field dict the policy engine evaluates against, from ORM
    rows (or any duck-typed object exposing the same attributes)."""
    return {
        "age": customer.age,
        "monthly_income": customer.monthly_income,
        "bureau_score": customer.bureau_score,
        "foir": customer.foir,
        "employment_tenure_months": customer.employment_tenure_months,
        "requested_amount": application.requested_amount,
    }
