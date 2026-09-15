"""
Placeholder document pipeline (security scan -> OCR -> classification ->
extraction -> validation, per the PRD). A real OCR/security-scan
integration is out of scope for this milestone -- this produces a
plausible confidence score synchronously so the rest of the system
(evidence checks, routing) has something real to react to, and is
deliberately isolated here so swapping in a real OCR provider later
touches exactly one function.
"""

from __future__ import annotations

import hashlib


def simulate_document_processing(application_id: str, document_type: str, file_name: str) -> dict:
    """
    Deterministic (not random) placeholder: derives a plausible OCR
    confidence from a hash of the inputs, so repeated calls in tests are
    stable. Replace with a real OCR call when one exists.
    """
    digest = hashlib.sha256(f"{application_id}:{document_type}:{file_name}".encode()).hexdigest()
    # Map the hash to a confidence mostly in a "good" band, occasionally low,
    # to keep the WAITING_FOR_DOCUMENT path exercisable in demos/tests.
    bucket = int(digest[:4], 16) % 100
    confidence = 0.55 + (bucket / 100) * 0.44  # ~0.55-0.99
    return {
        "status": "UPLOADED",
        "ocr_confidence": round(confidence, 3),
        "income_mismatch_ratio": round((int(digest[4:8], 16) % 20) / 100, 3),  # ~0.00-0.19
        "name_match": int(digest[8:9], 16) % 10 != 0,  # 90% match
    }
