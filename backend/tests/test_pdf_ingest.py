import pytest
import io

@pytest.mark.asyncio
async def test_pdf_ingest_and_coordinate_chunking(client, sample_pdf_bytes):
    # 1. Register Owner
    reg_payload = {
        "email": "owner_ingest@lab.org",
        "password": "Password123!",
        "full_name": "Lab Director",
        "role": "owner"
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get user's default collection
    colls_res = await client.get("/api/v1/collections", headers=headers)
    assert colls_res.status_code == 200
    collections = colls_res.json()
    assert len(collections) > 0
    collection_id = collections[0]["id"]

    # 3. Upload valid PDF
    files = {
        "file": ("trial_report.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    data = {
        "collection_id": collection_id,
        "title": "Adaptive Cognitive Protocols"
    }
    upload_res = await client.post("/api/v1/documents/upload", headers=headers, data=data, files=files)
    assert upload_res.status_code == 200, upload_res.text
    upload_data = upload_res.json()
    doc_id = upload_data["document"]["id"]
    assert upload_data["document"]["page_count"] == 2
    assert upload_data["chunks_created"] >= 2

    # 4. Fetch chunks and verify exact page numbers and coordinates
    chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) >= 2

    # Check page preservation
    page_numbers = {c["page_number"] for c in chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers

    # Check bounding box
    for c in chunks:
        assert c["bounding_box"] is not None
        assert "x0" in c["bounding_box"]
        assert "y0" in c["bounding_box"]
        assert "page_width" in c["bounding_box"]
        assert c["bounding_box"]["page_width"] == 595.0

    # 5. Reject invalid file type (e.g. .txt)
    txt_files = {
        "file": ("notes.txt", io.BytesIO(b"Simple plain text"), "text/plain")
    }
    txt_res = await client.post("/api/v1/documents/upload", headers=headers, data=data, files=txt_files)
    assert txt_res.status_code == 400
    assert "Only PDF documents" in txt_res.json()["detail"]

    # 6. Reject corrupted PDF with wrong magic bytes
    bad_pdf_files = {
        "file": ("fake.pdf", io.BytesIO(b"NOT_A_REAL_PDF_HEADER"), "application/pdf")
    }
    bad_pdf_res = await client.post("/api/v1/documents/upload", headers=headers, data=data, files=bad_pdf_files)
    assert bad_pdf_res.status_code == 400
    assert "not a valid PDF document" in bad_pdf_res.json()["detail"]
