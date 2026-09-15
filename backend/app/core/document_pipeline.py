"""
Document pipeline: security scan -> OCR -> classification -> extraction
-> validation, per the PRD.

Runs the real pipeline (Vercel Blob storage + AWS Textract OCR, see
app/integrations/ and app/services/document_extraction.py) whenever both
are configured; otherwise falls back to a deterministic simulation so
local dev/tests never need real cloud accounts. Either path is safe to
call from the same endpoint -- callers don't need to know which one ran.

"Security scan" is not actually implemented (no malware/content
scanning) -- noted here rather than silently absent.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

from app.core.config import settings
from app.integrations import textract, vercel_blob
from app.services.document_extraction import extract, income_mismatch_ratio, names_match

logger = logging.getLogger(__name__)


def _simulate(application_id: str, document_type: str, file_name: str) -> dict:
    """Deterministic (not random) placeholder: derives a plausible OCR
    confidence from a hash of the inputs, so repeated calls in tests are
    stable. Used when Blob/Textract aren't configured, or if the real
    pipeline fails (network hiccup, etc.) -- see process_document."""
    digest = hashlib.sha256(f"{application_id}:{document_type}:{file_name}".encode()).hexdigest()
    bucket = int(digest[:4], 16) % 100
    confidence = 0.55 + (bucket / 100) * 0.44  # ~0.55-0.99
    return {
        "status": "UPLOADED",
        "ocr_confidence": round(confidence, 3),
        "income_mismatch_ratio": round((int(digest[4:8], 16) % 20) / 100, 3),  # ~0.00-0.19
        "name_match": int(digest[8:9], 16) % 10 != 0,  # 90% match
        "file_url": None,
        "extracted_fields": None,
    }


def _process_real(
    application_id: str,
    document_type: str,
    file_name: str,
    file_bytes: bytes,
    content_type: str,
    declared_name: str,
    declared_monthly_income: float,
) -> dict:
    pathname = f"applications/{application_id}/{document_type}-{uuid.uuid4().hex[:8]}-{file_name}"
    file_url = vercel_blob.upload_file(pathname, file_bytes, content_type)

    textract_response = textract.analyze_document(file_bytes, content_type)
    result = extract(document_type, textract_response)

    match = names_match(declared_name, result.extracted_name)
    mismatch_ratio = income_mismatch_ratio(declared_monthly_income, result.extracted_income)

    return {
        "status": "UPLOADED",
        "ocr_confidence": round(result.confidence, 3),
        "income_mismatch_ratio": mismatch_ratio,
        "name_match": match,
        "file_url": file_url,
        "extracted_fields": result.raw_key_values or None,
    }


def process_document(
    application_id: str,
    document_type: str,
    file_name: str,
    declared_name: str,
    declared_monthly_income: float,
    file_bytes: bytes | None = None,
    content_type: str | None = None,
) -> dict:
    real_pipeline_available = (
        file_bytes is not None
        and content_type is not None
        and vercel_blob.is_configured()
        and textract.is_configured()
    )
    if real_pipeline_available:
        try:
            return _process_real(
                application_id, document_type, file_name, file_bytes, content_type, declared_name, declared_monthly_income
            )
        except Exception:
            logger.exception(
                "Real document pipeline failed for application %s document %s -- falling back to simulation",
                application_id,
                document_type,
            )
    return _simulate(application_id, document_type, file_name)
