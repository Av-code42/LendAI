"""Exercises the real multipart /documents endpoint end to end. AWS/Blob
credentials aren't configured in the test environment, so this covers the
simulated-fallback path of app/core/document_pipeline.py; the real-pipeline
path (Blob + Textract) is exercised by app/services/document_extraction.py's
own unit-level parsing logic instead, since it needs live cloud calls."""

from __future__ import annotations

from tests.test_golden_cases import APPLICANT


def _create_and_submit(client, **overrides) -> str:
    payload = {**APPLICANT, **overrides}
    resp = client.post("/applications", json=payload)
    assert resp.status_code == 201, resp.text
    app_id = resp.json()["application_id"]
    resp = client.post(f"/applications/{app_id}/submit")
    assert resp.status_code == 200
    return app_id


def test_upload_document_accepts_multipart_file(client):
    app_id = _create_and_submit(client)

    resp = client.post(
        f"/applications/{app_id}/documents",
        data={"document_type": "PAN"},
        files={"file": ("pan.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["document_type"] == "PAN"
    assert body["file_name"] == "pan.jpg"
    assert body["status"] == "UPLOADED"
    # No AWS/Blob credentials in the test env -> simulated fallback, which
    # never produces a real file_url or extracted_fields.
    assert body["file_url"] is None
    assert body["extracted_fields"] is None
    assert 0.0 <= body["ocr_confidence"] <= 1.0


def test_upload_document_moves_application_to_data_collection(client):
    app_id = _create_and_submit(client)

    resp = client.get(f"/applications/{app_id}")
    assert resp.json()["status"] == "SUBMITTED"

    client.post(
        f"/applications/{app_id}/documents",
        data={"document_type": "SALARY_SLIP"},
        files={"file": ("slip.pdf", b"fake-pdf-bytes", "application/pdf")},
    )

    resp = client.get(f"/applications/{app_id}")
    assert resp.json()["status"] == "DATA_COLLECTION"
