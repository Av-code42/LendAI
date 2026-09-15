"""
Pure-Python inference for a scikit-learn Pipeline(ColumnTransformer(
StandardScaler + OneHotEncoder), LogisticRegression) -- no numpy/scipy/
pandas/scikit-learn needed at serving time.

Logistic regression prediction is exactly reproducible as a dot product
plus a sigmoid; StandardScaler and OneHotEncoder are both simple enough
to reimplement directly. This exists purely to keep the deployed
function's dependency footprint small (see backend/README.md's "Deploying
to Vercel" section) -- scripts/export_lite_models.py is what proves this
produces the SAME numbers as the real sklearn pipeline, to high
precision, on real historical applications, before anything trusts it.

Only valid for a LogisticRegression-based pipeline. If a future retrain
picks Random Forest or XGBoost as the winner for either model, this
module can't represent it -- scoring.py falls back to the full
joblib+scikit-learn path in that case (see there).
"""

from __future__ import annotations

import json
import math
from pathlib import Path


class LiteLogisticModel:
    def __init__(self, spec: dict):
        self.numeric_features: list[str] = spec["numeric_features"]
        self.numeric_mean: list[float] = spec["numeric_mean"]
        self.numeric_scale: list[float] = spec["numeric_scale"]
        self.categorical_features: list[str] = spec["categorical_features"]
        self.categorical_categories: list[list[str]] = spec["categorical_categories"]
        self.coefficients: list[float] = spec["coefficients"]
        self.intercept: float = spec["intercept"]
        self.model_name: str = spec["model_name"]
        self.model_version: str = spec["model_version"]

        expected_len = len(self.numeric_features) + sum(len(c) for c in self.categorical_categories)
        if len(self.coefficients) != expected_len:
            raise ValueError(
                f"Lite model spec is inconsistent: {len(self.coefficients)} coefficients "
                f"but {expected_len} expected columns"
            )

    @classmethod
    def load(cls, path: Path) -> "LiteLogisticModel":
        with open(path) as f:
            return cls(json.load(f))

    def predict_proba(self, features: dict) -> float:
        z = self.intercept
        idx = 0
        for feat, mean, scale in zip(self.numeric_features, self.numeric_mean, self.numeric_scale):
            value = features[feat]
            scaled = (value - mean) / scale if scale else 0.0
            z += self.coefficients[idx] * scaled
            idx += 1
        for feat, categories in zip(self.categorical_features, self.categorical_categories):
            value = features[feat]
            for category in categories:
                if value == category:
                    z += self.coefficients[idx]
                idx += 1
        # sigmoid, overflow-safe for very negative/positive z
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        ez = math.exp(z)
        return ez / (1.0 + ez)
