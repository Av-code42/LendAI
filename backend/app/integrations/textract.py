"""
Minimal AWS Textract client -- calls the AnalyzeDocument JSON API
directly over HTTPS (signed with app/integrations/aws_sigv4.py), no
boto3. See that module's docstring for why.

AnalyzeDocument (the synchronous API used here) supports single-page
JPEG/PNG/PDF/TIFF only -- a genuine limitation for multi-page bank
statements, which Textract's async StartDocumentAnalysis API would
handle, at the cost of a polling flow instead of one request/response.
Sticking with the synchronous API for this MVP; documented here rather
than silently mishandled.
"""

from __future__ import annotations

import base64
import json

import httpx

from app.core.config import settings
from app.integrations.aws_sigv4 import signed_headers_for_json_post

SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf", "image/tiff"}


class TextractNotConfiguredError(RuntimeError):
    pass


class TextractError(RuntimeError):
    pass


class UnsupportedDocumentTypeError(TextractError):
    pass


def is_configured() -> bool:
    return bool(settings.aws_access_key_id and settings.aws_secret_access_key)


def analyze_document(file_bytes: bytes, content_type: str) -> dict:
    """Returns Textract's raw AnalyzeDocument response (a dict with a
    "Blocks" list) for the given file. Requests both FORMS (key/value
    pairs) and TABLES analysis."""
    if not is_configured():
        raise TextractNotConfiguredError("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY are not set")
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise UnsupportedDocumentTypeError(
            f"Textract's synchronous API doesn't support {content_type!r} "
            f"(supported: {sorted(SUPPORTED_CONTENT_TYPES)})"
        )

    region = settings.aws_region
    host = f"textract.{region}.amazonaws.com"
    payload = json.dumps(
        {
            "Document": {"Bytes": base64.b64encode(file_bytes).decode("ascii")},
            "FeatureTypes": ["FORMS", "TABLES"],
        }
    ).encode("utf-8")

    headers = signed_headers_for_json_post(
        access_key=settings.aws_access_key_id,
        secret_key=settings.aws_secret_access_key,
        region=region,
        service="textract",
        host=host,
        uri="/",
        payload=payload,
        amz_target="Textract.AnalyzeDocument",
    )
    headers["Host"] = host

    resp = httpx.post(f"https://{host}/", headers=headers, content=payload, timeout=30.0)
    if resp.status_code != 200:
        raise TextractError(f"Textract AnalyzeDocument failed ({resp.status_code}): {resp.text}")
    return resp.json()
