import pytest
import io
from backend.app.services.acl_service import get_permitted_document_ids

@pytest.mark.asyncio
async def test_negative_authorization_controls(client, db_session, sample_pdf_bytes):
    # 1. Register User A (Owner of Workspace A)
    user_a_res = await client.post("/api/v1/auth/register", json={
        "email": "owner_alice@lab-a.org",
        "password": "Password123!",
        "full_name": "Alice Owner",
        "role": "owner"
    })
    token_a = user_a_res.json()["access_token"]
    user_a_id = user_a_res.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Get User A's collection and upload restricted Paper A
    colls_a_res = await client.get("/api/v1/collections", headers=headers_a)
    col_a_id = colls_a_res.json()[0]["id"]

    upload_res = await client.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        data={"collection_id": col_a_id, "title": "Confidential Study A"},
        files={"file": ("study_a.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    )
    assert upload_res.status_code == 200
    doc_a_id = upload_res.json()["document"]["id"]

    # 3. Register User B (Independent Researcher in Workspace B)
    user_b_res = await client.post("/api/v1/auth/register", json={
        "email": "unauthorized_bob@lab-b.org",
        "password": "Password123!",
        "full_name": "Bob External",
        "role": "researcher"
    })
    token_b = user_b_res.json()["access_token"]
    user_b_id = user_b_res.json()["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # --- NEGATIVE TEST 1: User B cannot view Document A metadata ---
    doc_meta_res = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
    assert doc_meta_res.status_code == 403, "Security Failure: Unauthorized user was able to fetch restricted document metadata!"
    assert "Access denied" in doc_meta_res.json()["detail"]

    # --- NEGATIVE TEST 2: User B cannot retrieve Document A passage chunks ---
    chunks_res = await client.get(f"/api/v1/documents/{doc_a_id}/chunks", headers=headers_b)
    assert chunks_res.status_code == 403, "Security Failure: Unauthorized user was able to fetch passage chunks!"
    assert "Access denied" in chunks_res.json()["detail"]

    # --- NEGATIVE TEST 3: User B cannot stream raw Document A PDF file ---
    file_stream_res = await client.get(f"/api/v1/documents/{doc_a_id}/file", headers=headers_b)
    assert file_stream_res.status_code == 403, "Security Failure: Unauthorized user was able to stream restricted PDF!"

    # --- NEGATIVE TEST 4: Pre-retrieval ACL filter verification ---
    # User B listing documents must return empty list (Doc A is excluded BEFORE retrieval)
    list_docs_b = await client.get("/api/v1/documents", headers=headers_b)
    assert list_docs_b.status_code == 200
    b_doc_ids = [d["id"] for d in list_docs_b.json()]
    assert doc_a_id not in b_doc_ids

    # Query get_permitted_document_ids directly
    permitted_for_b = await get_permitted_document_ids(db_session, user_b_id)
    assert doc_a_id not in permitted_for_b, "Security Failure: Restricted doc ID leaked into pre-retrieval whitelist!"

    # --- NEGATIVE TEST 5: Viewer cannot upload to collection (Role Hierarchy) ---
    # Register User C as Viewer in Collection A's workspace
    user_c_res = await client.post("/api/v1/auth/register", json={
        "email": "viewer_charlie@lab-a.org",
        "password": "Password123!",
        "full_name": "Charlie Viewer",
        "role": "viewer"
    })
    token_c = user_c_res.json()["access_token"]
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # Charlie attempts to upload to Alice's collection
    unauth_upload = await client.post(
        "/api/v1/documents/upload",
        headers=headers_c,
        data={"collection_id": col_a_id, "title": "Unauthorized Upload Attempt"},
        files={"file": ("unauth.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    )
    assert unauth_upload.status_code == 403, "Security Failure: Viewer without reviewer/owner role was allowed to upload!"
    assert "Access denied" in unauth_upload.json()["detail"]
