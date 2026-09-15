"""
Trains and evaluates Logistic Regression / Random Forest / XGBoost for
both the credit (default) and fraud models, per the PRD. The best model
per target (by PR-AUC on a held-out test split) is saved as the artifact
the scoring service loads; metrics for all three are saved alongside for
comparison/audit.

Run: python -m app.ml.train   (or scripts/train_models.py)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.core.config import MODELS_DIR
from app.db.base import SessionLocal
from app.ml.features import (
    CREDIT_CATEGORICAL_FEATURES,
    CREDIT_NUMERIC_FEATURES,
    FRAUD_CATEGORICAL_FEATURES,
    FRAUD_NUMERIC_FEATURES,
    build_credit_training_frame,
    build_fraud_training_frame,
)

RANDOM_STATE = 42
TEST_SIZE = 0.3
DECISION_THRESHOLD = 0.5


@dataclass
class ModelMetrics:
    algorithm: str
    pr_auc: float
    precision_at_threshold: float
    recall_at_threshold: float
    false_positive_rate: float
    false_negative_rate: float
    positive_rate_in_test: float
    n_test: int


def _make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    transformers = [("num", StandardScaler(), numeric)]
    if categorical:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore"), categorical))
    return ColumnTransformer(transformers)


def _candidates(pos_weight: float) -> dict[str, object]:
    return {
        "LOGISTIC_REGRESSION": LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "RANDOM_FOREST": RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "XGBOOST": XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            scale_pos_weight=pos_weight,
            eval_metric="aucpr",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def _evaluate(y_true, y_score) -> ModelMetrics:
    y_pred = (y_score >= DECISION_THRESHOLD).astype(int)
    pr_auc = average_precision_score(y_true, y_score)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    return ModelMetrics(
        algorithm="",  # filled by caller
        pr_auc=float(pr_auc),
        precision_at_threshold=float(precision),
        recall_at_threshold=float(recall),
        false_positive_rate=float(fpr),
        false_negative_rate=float(fnr),
        positive_rate_in_test=float(np.mean(y_true)),
        n_test=int(len(y_true)),
    )


def _train_and_compare(
    X: pd.DataFrame, y: pd.Series, numeric: list[str], categorical: list[str]
) -> tuple[str, Pipeline, dict[str, ModelMetrics]]:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    results: dict[str, ModelMetrics] = {}
    pipelines: dict[str, Pipeline] = {}

    for name, clf in _candidates(pos_weight).items():
        pipe = Pipeline([("prep", _make_preprocessor(numeric, categorical)), ("clf", clf)])
        pipe.fit(X_train, y_train)
        y_score = pipe.predict_proba(X_test)[:, 1]
        metrics = _evaluate(y_test, y_score)
        metrics.algorithm = name
        results[name] = metrics
        pipelines[name] = pipe

    best_name = max(results, key=lambda n: results[n].pr_auc)

    # Refit the winner on the FULL dataset so the shipped artifact benefits
    # from all available data, not just the training split.
    best_pipe = Pipeline([("prep", _make_preprocessor(numeric, categorical)), ("clf", _candidates(pos_weight)[best_name])])
    best_pipe.fit(X, y)

    return best_name, best_pipe, results


def train_all() -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    session = SessionLocal()
    report: dict = {}
    try:
        # --- credit ---
        X, y = build_credit_training_frame(session)
        best_name, best_pipe, results = _train_and_compare(
            X, y, CREDIT_NUMERIC_FEATURES, CREDIT_CATEGORICAL_FEATURES
        )
        version = "credit-ml-v1"
        joblib.dump({"pipeline": best_pipe, "algorithm": best_name, "version": version}, MODELS_DIR / "credit_model.joblib")
        report["credit"] = {
            "best_algorithm": best_name,
            "version": version,
            "n_samples": len(X),
            "results": {k: asdict(v) for k, v in results.items()},
        }
        print(f"[credit] best={best_name} pr_auc={results[best_name].pr_auc:.4f}")

        # --- fraud ---
        X, y = build_fraud_training_frame(session)
        best_name, best_pipe, results = _train_and_compare(
            X, y, FRAUD_NUMERIC_FEATURES, FRAUD_CATEGORICAL_FEATURES
        )
        version = "fraud-ml-v1"
        joblib.dump({"pipeline": best_pipe, "algorithm": best_name, "version": version}, MODELS_DIR / "fraud_model.joblib")
        report["fraud"] = {
            "best_algorithm": best_name,
            "version": version,
            "n_samples": len(X),
            "results": {k: asdict(v) for k, v in results.items()},
        }
        print(f"[fraud] best={best_name} pr_auc={results[best_name].pr_auc:.4f}")
    finally:
        session.close()

    with open(MODELS_DIR / "training_report.json", "w") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    train_all()
