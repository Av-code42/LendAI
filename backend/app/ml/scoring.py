"""
Scoring service: loads the trained model artifacts once and exposes
score_credit / score_fraud, each returning a (score, risk_level) pair and
persisting an immutable ModelOutput row (PRD: "Store model_version with
every score.").

Prefers the pure-Python "lite" scorer (app/ml/lite.py) over the full
joblib+scikit-learn pipeline whenever a lite spec has been exported for
that model (scripts/export_lite_models.py) -- numerically validated to
match the real pipeline to floating-point-epsilon precision across every
application in the database. This is what lets the deployed function
avoid bundling scikit-learn/scipy/pandas/numpy at all (see
backend/README.md's "Deploying to Vercel" section). Falls back to the
full sklearn pipeline if no lite spec exists yet, or if a future retrain
picks a non-LogisticRegression winner (see app/ml/lite.py's docstring) --
that fallback path needs the full requirements.txt installed (true for
local/Docker; NOT true for the slim Vercel deployment, which is exactly
why export_lite_models.py refuses to export a spec that doesn't match).

Risk-band thresholds are chosen to match the historical dataset's own
credit_risk_band / fraud_risk_band boundaries (see
scripts/validate_policy.py-style inspection during development), so our
live-scored risk levels stay comparable to the historical rows loaded
by scripts/load_data.py.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.config import MODELS_DIR
from app.db import models as m
from app.ml.inference_features import fetch_credit_features, fetch_fraud_features
from app.ml.lite import LiteLogisticModel

CREDIT_THRESHOLDS = (0.10, 0.25)  # < low -> LOW, < high -> MEDIUM, else HIGH
FRAUD_THRESHOLDS = (0.20, 0.45)


class ModelNotTrainedError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_credit_model():
    lite_path = MODELS_DIR / "credit_model_lite.json"
    if lite_path.exists():
        return LiteLogisticModel.load(lite_path)
    return _load_full_sklearn_pipeline("credit_model.joblib")


@lru_cache(maxsize=1)
def _load_fraud_model():
    lite_path = MODELS_DIR / "fraud_model_lite.json"
    if lite_path.exists():
        return LiteLogisticModel.load(lite_path)
    return _load_full_sklearn_pipeline("fraud_model.joblib")


def _load_full_sklearn_pipeline(filename: str):
    # Imported lazily: this path is only exercised when no lite spec
    # exists (a non-LogisticRegression winner), and importing joblib here
    # keeps it out of the module's top-level import graph for the slim
    # Vercel deployment, which never has scikit-learn installed.
    import joblib

    path = MODELS_DIR / filename
    if not path.exists():
        raise ModelNotTrainedError(f"{filename} not found -- run `python -m app.ml.train`.")
    return joblib.load(path)


def _predict(model, features: dict, row_builder) -> tuple[float, str, str]:
    """Returns (score, model_name, model_version) for either a
    LiteLogisticModel or a full joblib sklearn artifact dict."""
    if isinstance(model, LiteLogisticModel):
        return model.predict_proba(features), model.model_name, model.model_version
    score = float(model["pipeline"].predict_proba(row_builder())[:, 1][0])
    return score, model["algorithm"], model["version"]


def _risk_level(score: float, thresholds: tuple[float, float]) -> str:
    low, high = thresholds
    if score < low:
        return m.RiskLevel.LOW.value
    if score < high:
        return m.RiskLevel.MEDIUM.value
    return m.RiskLevel.HIGH.value


def score_credit(session: Session, application_id: str) -> m.ModelOutput:
    model = _load_credit_model()
    features = fetch_credit_features(session, application_id)

    def _row():
        from app.ml.features import build_credit_inference_row

        return build_credit_inference_row(session, application_id)

    score, model_name, model_version = _predict(model, features, _row)
    output = m.ModelOutput(
        application_id=application_id,
        model_type=m.ModelType.CREDIT.value,
        model_name=model_name,
        model_version=model_version,
        score=score,
        risk_level=_risk_level(score, CREDIT_THRESHOLDS),
    )
    session.add(output)
    session.flush()
    return output


def score_fraud(session: Session, application_id: str) -> m.ModelOutput:
    model = _load_fraud_model()
    features = fetch_fraud_features(session, application_id)

    def _row():
        from app.ml.features import build_fraud_inference_row

        return build_fraud_inference_row(session, application_id)

    score, model_name, model_version = _predict(model, features, _row)
    output = m.ModelOutput(
        application_id=application_id,
        model_type=m.ModelType.FRAUD.value,
        model_name=model_name,
        model_version=model_version,
        score=score,
        risk_level=_risk_level(score, FRAUD_THRESHOLDS),
    )
    session.add(output)
    session.flush()
    return output
