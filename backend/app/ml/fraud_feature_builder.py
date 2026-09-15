"""
Computes a FraudFeatures row for a live (newly submitted) application.

The historical dataset's fraud_features.csv came from systems this MVP
doesn't have yet (device fingerprinting, geolocation) -- so for a new
application we approximate what we honestly can from data actually
available at this stage, and default the rest to a neutral value rather
than fabricate a signal. This is a documented MVP limitation, not a
finished fraud-signal pipeline.

Real signal, computed live:
- applications_last_7d / device_reuse_count_30d: approximated as this
  customer's OTHER application count in the window (a real velocity
  signal, though customer-level rather than device/IP-level).
- bank_account_age_months: proxied from the customer's banking
  relationship tenure (relationship_months) -- the closest thing we
  actually have to "how long has this account existed".
- document_anomaly_score / income_mismatch_score: derived from the
  documents actually uploaded for this application.

Defaulted (no live capability yet):
- location_mismatch: always 0 -- no geolocation capture in this MVP.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import models as m


def ensure_fraud_features(session, application_id: str) -> m.FraudFeatures:
    existing = session.get(m.FraudFeatures, application_id)
    if existing is not None:
        return existing

    app = session.get(m.Application, application_id)
    customer = session.get(m.Customer, app.customer_id)
    now = app.created_at or datetime.now(timezone.utc)

    other_apps = session.execute(
        select(m.Application).where(
            m.Application.customer_id == customer.customer_id,
            m.Application.application_id != application_id,
        )
    ).scalars().all()

    def _naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    now_n = _naive(now)
    applications_last_7d = sum(1 for a in other_apps if now_n - _naive(a.created_at) <= timedelta(days=7))
    device_reuse_count_30d = sum(1 for a in other_apps if now_n - _naive(a.created_at) <= timedelta(days=30))

    documents = session.execute(
        select(m.Document).where(m.Document.application_id == application_id)
    ).scalars().all()
    if documents:
        document_anomaly_score = round(
            sum(1 - (d.ocr_confidence or 1.0) for d in documents) / len(documents), 4
        )
        income_mismatch_score = max((d.income_mismatch_ratio or 0.0) for d in documents)
    else:
        document_anomaly_score = 0.0
        income_mismatch_score = 0.0

    features = m.FraudFeatures(
        application_id=application_id,
        device_reuse_count_30d=device_reuse_count_30d,
        applications_last_7d=applications_last_7d,
        location_mismatch=0,
        bank_account_age_months=customer.relationship_months,
        document_anomaly_score=document_anomaly_score,
        income_mismatch_score=income_mismatch_score,
        fraud_label=None,
    )
    session.add(features)
    session.flush()
    return features
