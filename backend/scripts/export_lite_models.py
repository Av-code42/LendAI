"""
Distills the trained joblib LogisticRegression pipelines
(artifacts/models/{credit,fraud}_model.joblib) into small, dependency-free
JSON specs (artifacts/models/{credit,fraud}_model_lite.json) that
app/ml/lite.py can score without numpy/scipy/pandas/scikit-learn.

Requires the FULL requirements.txt (this needs scikit-learn to load the
joblib artifact) -- run this locally/offline after training, not as part
of the deployed function. Only supports a LogisticRegression winner; see
app/ml/lite.py's docstring for what happens if a future retrain picks a
tree-based model instead.

Validates the exported lite model against the real sklearn pipeline on
every application currently in the database before writing anything, and
refuses to export if they don't match to high precision -- this is what
actually justifies trusting a hand-reimplemented scorer in production.

Usage: python scripts/export_lite_models.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from app.core.config import MODELS_DIR  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.db import models as m  # noqa: E402
from app.ml.features import (  # noqa: E402
    CREDIT_CATEGORICAL_FEATURES,
    CREDIT_NUMERIC_FEATURES,
    FRAUD_CATEGORICAL_FEATURES,
    FRAUD_NUMERIC_FEATURES,
    build_credit_inference_row,
    build_fraud_inference_row,
)
from app.ml.inference_features import fetch_credit_features, fetch_fraud_features  # noqa: E402
from app.ml.lite import LiteLogisticModel  # noqa: E402

MAX_ALLOWED_DIFF = 1e-6


def export_one(
    artifact_name: str,
    lite_name: str,
    model_type: str,
    numeric_features: list[str],
    categorical_features: list[str],
    session,
    fetch_row,
    fetch_dict,
):
    artifact = joblib.load(MODELS_DIR / artifact_name)
    pipeline = artifact["pipeline"]
    algorithm = artifact["algorithm"]

    if algorithm != "LOGISTIC_REGRESSION":
        print(f"[{model_type}] winner is {algorithm}, not LOGISTIC_REGRESSION -- skipping lite export.")
        print(f"[{model_type}] the deployed (Vercel) function needs the full sklearn path for this model.")
        return

    clf: LogisticRegression = pipeline.named_steps["clf"]
    prep = pipeline.named_steps["prep"]
    scaler = prep.named_transformers_["num"]

    spec = {
        "model_name": algorithm,
        "model_version": artifact["version"],
        "numeric_features": numeric_features,
        "numeric_mean": scaler.mean_.tolist(),
        "numeric_scale": scaler.scale_.tolist(),
        "categorical_features": categorical_features,
        "categorical_categories": [],
        "coefficients": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
    }
    if categorical_features:
        encoder = prep.named_transformers_["cat"]
        spec["categorical_categories"] = [cats.tolist() for cats in encoder.categories_]

    lite_model = LiteLogisticModel(spec)

    # --- validate against the real pipeline on every application in the DB ---
    app_ids = [row[0] for row in session.execute(select(m.Application.application_id)).all()]
    max_diff = 0.0
    checked = 0
    for app_id in app_ids:
        try:
            row_df = fetch_row(session, app_id)
            feature_dict = fetch_dict(session, app_id)
        except ValueError:
            continue
        real_proba = float(pipeline.predict_proba(row_df)[:, 1][0])
        lite_proba = lite_model.predict_proba(feature_dict)
        diff = abs(real_proba - lite_proba)
        max_diff = max(max_diff, diff)
        checked += 1

    print(f"[{model_type}] validated {checked} applications, max |diff| = {max_diff:.2e}")
    if max_diff > MAX_ALLOWED_DIFF:
        raise SystemExit(
            f"[{model_type}] lite model diverges from the real pipeline by {max_diff:.2e} "
            f"(> {MAX_ALLOWED_DIFF:.0e}) -- refusing to export. Check feature ordering/semantics "
            f"in app/ml/inference_features.py against app/ml/features.py."
        )

    out_path = MODELS_DIR / lite_name
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"[{model_type}] wrote {out_path}")


def main():
    session = SessionLocal()
    try:
        export_one(
            "credit_model.joblib",
            "credit_model_lite.json",
            "credit",
            CREDIT_NUMERIC_FEATURES,
            CREDIT_CATEGORICAL_FEATURES,
            session,
            build_credit_inference_row,
            fetch_credit_features,
        )
        export_one(
            "fraud_model.joblib",
            "fraud_model_lite.json",
            "fraud",
            FRAUD_NUMERIC_FEATURES,
            FRAUD_CATEGORICAL_FEATURES,
            session,
            build_fraud_inference_row,
            fetch_fraud_features,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
