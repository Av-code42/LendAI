"""
Minimal Vercel Blob client using its plain HTTPS REST API directly --
there is no official Python SDK (only the JS/TS `@vercel/blob` package),
so this hand-rolls the PUT request the SDK itself makes.

Docs: https://vercel.com/docs/storage/vercel-blob/rest-api

If this doesn't match Vercel's actual current contract exactly, the
error raised includes the full response body specifically so a
real-world failure is immediately actionable rather than a bare status
code.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

BLOB_API_BASE = "https://blob.vercel-storage.com"
BLOB_API_VERSION = "7"


class BlobNotConfiguredError(RuntimeError):
    pass


class BlobUploadError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.blob_read_write_token)


def upload_file(pathname: str, content: bytes, content_type: str) -> str:
    """Uploads `content` to Vercel Blob at (a possibly-suffixed) `pathname`
    and returns the public URL. Raises BlobNotConfiguredError if no token
    is set, or BlobUploadError on any non-2xx response."""
    if not settings.blob_read_write_token:
        raise BlobNotConfiguredError("BLOB_READ_WRITE_TOKEN is not set")

    url = f"{BLOB_API_BASE}/{pathname}"
    headers = {
        "Authorization": f"Bearer {settings.blob_read_write_token}",
        "x-api-version": BLOB_API_VERSION,
        "x-content-type": content_type,
        "x-add-random-suffix": "1",
    }
    resp = httpx.put(url, headers=headers, content=content, timeout=30.0)
    if resp.status_code >= 300:
        raise BlobUploadError(f"Vercel Blob upload failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    blob_url = data.get("url")
    if not blob_url:
        raise BlobUploadError(f"Vercel Blob upload response missing 'url': {data}")
    return blob_url
