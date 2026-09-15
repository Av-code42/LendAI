"""
The deterministic decision router -- PRD order, exactly:

1. HIGH fraud -> HUMAN_REVIEW
2. Policy failure -> DECLINED
3. HIGH credit risk -> HUMAN_REVIEW
4. MEDIUM fraud -> HUMAN_REVIEW
5. Missing/low-confidence evidence -> HUMAN_REVIEW or WAITING_FOR_DOCUMENT
6. Otherwise -> AUTO_APPROVE

This is the single place that turns model/policy/evidence signals into a
status. Nothing upstream (agent, API handler) is allowed to compute a
routing outcome itself -- they gather signals and call `route()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models import ApplicationStatus as S


@dataclass
class EvidenceSignal:
    ok: bool
    missing_document_types: list[str] = field(default_factory=list)
    low_confidence_document_types: list[str] = field(default_factory=list)
    mismatch_document_types: list[str] = field(default_factory=list)

    @property
    def needs_document(self) -> bool:
        """Fixable by asking for a (re-)upload."""
        return bool(self.missing_document_types or self.low_confidence_document_types)

    @property
    def needs_review(self) -> bool:
        """Not fixable by re-upload -- evidence contradicts the claim."""
        return bool(self.mismatch_document_types)


@dataclass
class RoutingSignals:
    fraud_risk: str  # LOW | MEDIUM | HIGH
    credit_risk: str  # LOW | MEDIUM | HIGH
    policy_pass: bool
    policy_failed_reason_codes: list[str]
    evidence: EvidenceSignal


@dataclass
class RoutingDecision:
    status: str
    reason_codes: list[str]


def route(signals: RoutingSignals) -> RoutingDecision:
    if signals.fraud_risk == "HIGH":
        return RoutingDecision(S.HUMAN_REVIEW.value, ["HIGH_FRAUD_RISK"])

    if not signals.policy_pass:
        return RoutingDecision(S.DECLINED.value, list(signals.policy_failed_reason_codes))

    if signals.credit_risk == "HIGH":
        return RoutingDecision(S.HUMAN_REVIEW.value, ["HIGH_CREDIT_RISK"])

    if signals.fraud_risk == "MEDIUM":
        return RoutingDecision(S.HUMAN_REVIEW.value, ["MEDIUM_FRAUD_RISK"])

    if not signals.evidence.ok:
        if signals.evidence.needs_review:
            return RoutingDecision(S.HUMAN_REVIEW.value, ["DOCUMENT_MISMATCH"])
        return RoutingDecision(S.WAITING_FOR_DOCUMENT.value, ["LOW_DOCUMENT_CONFIDENCE"])

    return RoutingDecision(S.AUTO_APPROVED.value, ["ALL_POLICY_RULES_PASS", "LOW_FRAUD_RISK", "LOW_CREDIT_RISK"])
