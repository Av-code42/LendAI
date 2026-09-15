from __future__ import annotations

from app.core.config import settings
from app.db import models as m
from app.routing.router import EvidenceSignal

REQUIRED_DOCUMENT_TYPES = ["PAN", "SALARY_SLIP", "BANK_STATEMENT"]

# NOTE on income_mismatch_ratio / name_match: these are stored and shown to
# underwriters (real signal for human judgement), but empirically they do
# NOT drive the historical dataset's routing outcome -- a document with
# name_match=False was found auto-approved in the historical data, and
# income_mismatch_ratio does not separate reviewed from non-reviewed
# applications. So they are deliberately NOT used to force WAITING_FOR_
# DOCUMENT/HUMAN_REVIEW here; only OCR confidence (an explicit PRD
# requirement -- "Low OCR confidence ... cannot silently pass") does.


def check_evidence(documents: list[m.Document]) -> EvidenceSignal:
    by_type: dict[str, m.Document] = {}
    for d in documents:
        # last one wins, i.e. a re-upload supersedes the prior attempt
        by_type[d.document_type] = d

    missing = [t for t in REQUIRED_DOCUMENT_TYPES if t not in by_type]
    low_confidence = [
        t
        for t, d in by_type.items()
        if d.ocr_confidence is not None and d.ocr_confidence < settings.ocr_confidence_floor
    ]

    ok = not missing and not low_confidence
    return EvidenceSignal(
        ok=ok,
        missing_document_types=missing,
        low_confidence_document_types=low_confidence,
        mismatch_document_types=[],
    )
