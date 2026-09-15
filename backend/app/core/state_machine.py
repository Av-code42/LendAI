"""
The application state machine. This module is the single source of
truth for legal transitions -- the API layer and the agent orchestrator
both call `transition()` rather than writing `application.status = ...`
directly, so an illegal jump (whoever requests it, human, agent, or a
bug) is rejected before it ever reaches the database.

DRAFT -> SUBMITTED -> DATA_COLLECTION -> VERIFICATION -> RISK_ASSESSMENT
      -> POLICY_EVALUATION -> {AUTO_APPROVED | HUMAN_REVIEW | DECLINED}
      -> OFFER -> AGREEMENT -> MOCK_DISBURSAL

WAITING_FOR_DOCUMENT is a side-branch reachable from DATA_COLLECTION,
VERIFICATION, or HUMAN_REVIEW (a REQUEST_INFORMATION decision) whenever
evidence is missing or low-confidence, per the PRD decision router.
"""

from __future__ import annotations

from app.db.models import ApplicationStatus as S

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    S.DRAFT.value: {S.SUBMITTED.value},
    S.SUBMITTED.value: {S.DATA_COLLECTION.value},
    S.DATA_COLLECTION.value: {S.VERIFICATION.value, S.WAITING_FOR_DOCUMENT.value},
    S.WAITING_FOR_DOCUMENT.value: {S.DATA_COLLECTION.value, S.VERIFICATION.value},
    S.VERIFICATION.value: {S.RISK_ASSESSMENT.value, S.WAITING_FOR_DOCUMENT.value},
    S.RISK_ASSESSMENT.value: {S.POLICY_EVALUATION.value},
    S.POLICY_EVALUATION.value: {S.AUTO_APPROVED.value, S.HUMAN_REVIEW.value, S.DECLINED.value},
    S.HUMAN_REVIEW.value: {S.OFFER.value, S.DECLINED.value, S.WAITING_FOR_DOCUMENT.value, S.HUMAN_REVIEW.value},
    S.AUTO_APPROVED.value: {S.OFFER.value},
    S.OFFER.value: {S.AGREEMENT.value},
    S.AGREEMENT.value: {S.MOCK_DISBURSAL.value},
    S.DECLINED.value: set(),
    S.MOCK_DISBURSAL.value: set(),
}


class InvalidTransitionError(Exception):
    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition application from {current} to {target}")


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def require_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
