"""
Hand-rolled AWS Signature Version 4 signer for calling Textract's JSON
API directly over HTTPS. Deliberately not using boto3: boto3/botocore
bundle service-model JSON for every AWS service regardless of which one
you call, which would reintroduce the exact bundle-size problem already
fought and fixed for the Vercel deployment (see backend/README.md's
"Deploying to Vercel" section) -- this is maybe 100 lines of stdlib-only
code against AWS's own published algorithm, vs. reopening that fight.

Reference: https://docs.aws.amazon.com/general/latest/gr/sigv4-signing-with-a-body.html
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def signed_headers_for_json_post(
    *,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    host: str,
    uri: str,
    payload: bytes,
    amz_target: str,
) -> dict[str, str]:
    """Returns the full header set (including Authorization) needed to
    make a signed POST of `payload` (JSON bytes) to https://{host}{uri}."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    content_type = "application/x-amz-json-1.1"
    payload_hash = hashlib.sha256(payload).hexdigest()

    # Headers that get signed must be included, sorted, in both the
    # canonical request and the signed_headers list, exactly as sent.
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{amz_target}\n"
    )
    signed_headers = "content-type;host;x-amz-date;x-amz-target"

    canonical_request = "\n".join(
        [
            "POST",
            uri,
            "",  # no query string
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    signing_key = _signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Content-Type": content_type,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": amz_target,
        "Authorization": authorization,
    }
