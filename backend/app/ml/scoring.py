"""
Scoring service: loads the trained model artifacts once and exposes
score_credit / score_fraud, each returning a (score, risk_level) pair and
persisting an immutable ModelOutput row (PRD: "Store model_version with
every score.").

Risk-band thresholds are chosen to match the historical dataset's own
credit_risk_band / fraud_risk_band boundaries (see
scripts/validate_policy.py-style inspection during development), so our
live-scored risk levels stay comparable to the historical rows loaded
by scripts/load_data.py.
"""

from __future__ import annotations

from functools import lru_cache

import joblib
from sqlalchemy.orm import Session

from app.core.config import MODELS_DIR
from app.db import models as m
from app.ml.features import build_credit_inference_row, build_fraud_inference_row

CREDIT_THRESHOLDS = (0.10, 0.25)  # < low -> LOW, < high -> MEDIUM, else HIGH
FRAUD_THRESHOLDS = (0.20, 0.45)


class ModelNotTrainedError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_credit_artifact():
    path = MODELS_DIR / "credit_model.joblib"
    if not path.exists():
        raise ModelNotTrainedError("Credit model not trained yet -- run `python -m app.ml.train`.")
    return joblib.load(path)


@lru_cache(maxsize=1)
def _load_fraud_artifact():
    path = MODELS_DIR / "fraud_model.joblib"
    if not path.exists():
        raise ModelNotTrainedError("Fraud model not trained yet -- run `python -m app.ml.train`.")
    return joblib.load(path)


def _risk_level(score: float, thresholds: tuple[float, float]) -> str:
    low, high = thresholds
    if score < low:
        return m.RiskLevel.LOW.value
    if score < high:
        return m.RiskLevel.MEDIUM.value
    return m.RiskLevel.HIGH.value


def score_credit(session: Session, application_id: str) -> m.ModelOutput:
    artifact = _load_credit_artifact()
    row = build_credit_inference_row(session, application_id)
    score = float(artifact["pipeline"].predict_proba(row)[:, 1][0])
    output = m.ModelOutput(
        application_id=application_id,
        model_type=m.ModelType.CREDIT.value,
        model_name=artifact["algorithm"],
        model_version=artifact["version"],
        score=score,
        risk_level=_risk_level(score, CREDIT_THRESHOLDS),
    )
    session.add(output)
    session.flush()
    return output


def score_fraud(session: Session, application_id: str) -> m.ModelOutput:
    artifact = _load_fraud_artifact()
    row = build_fraud_inference_row(session, application_id)
    score = float(artifact["pipeline"].predict_proba(row)[:, 1][0])
    output = m.ModelOutput(
        application_id=application_id,
        model_type=m.ModelType.FRAUD.value,
        model_name=artifact["algorithm"],
        model_version=artifact["version"],
        score=score,
        risk_level=_risk_level(score, FRAUD_THRESHOLDS),
    )
    session.add(output)
    session.flush()
    return output
