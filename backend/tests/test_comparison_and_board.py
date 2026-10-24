import pytest
import io
import fitz

def make_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

@pytest.mark.asyncio
async def test_4d_comparability_guard_prevents_false_contradiction(client):
    """
    Core principle: Before calling studies 'contradictory', check differences in:
    population/dataset, setting, method, and outcome measure.
    If they differ, label the result 'not directly comparable' and explain why.
    """
    # 1. Register owner
    reg = await client.post("/api/v1/auth/register", json={
        "email": "prof_comparative@lab.edu",
        "password": "Password123!",
        "full_name": "Prof Comparative",
        "role": "owner"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    col = (await client.post("/api/v1/collections", json={"name": "Comparison Study Set"}, headers=headers)).json()

    # Document 1: Evaluated on synthetic math benchmark, claims method outperforms
    doc1_text = (
        "Primary Objective: Evaluate direct alignment on synthetic reasoning tasks. "
        "Methodology: Direct preference optimization with greedy search decoding. "
        "Participants Cohort: GSM8K synthetic math benchmark dataset. "
        "Findings and Results: Direct alignment decisively outperforms baseline supervised fine-tuning by 14%."
    )
    doc1_up = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Direct Alignment on Synthetic Reasoning"},
        files={"file": ("study1.pdf", io.BytesIO(make_test_pdf(doc1_text)), "application/pdf")},
        headers=headers
    )
    doc1_id = doc1_up.json()["document"]["id"]
    await client.post(f"/api/v1/documents/{doc1_id}/extractions/extract", headers=headers)

    # Document 2: Evaluated on clinical hospital transcripts, claims method underperforms
    doc2_text = (
        "Primary Objective: Investigate clinician alignment in emergency department triage. "
        "Methodology: Reinforcement learning with physician feedback protocols. "
        "Participants Cohort: Multi-center emergency department ICU patient records. "
        "Findings and Results: Direct alignment underperforms conventional rule-based clinical checklists in high-stakes triage."
    )
    doc2_up = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Clinical Trial Realities in Dialogue Models"},
        files={"file": ("study2.pdf", io.BytesIO(make_test_pdf(doc2_text)), "application/pdf")},
        headers=headers
    )
    doc2_id = doc2_up.json()["document"]["id"]
    await client.post(f"/api/v1/documents/{doc2_id}/extractions/extract", headers=headers)

    # 2. Run cross-study comparison
    comp_res = await client.post("/api/v1/comparison/matrix", json={
        "question": "How does preference alignment compare to baselines?",
        "document_ids": [doc1_id, doc2_id]
    }, headers=headers)
    assert comp_res.status_code == 200
    comp_data = comp_res.json()

    assert len(comp_data["studies"]) == 2
    assert len(comp_data["pairwise_comparisons"]) == 1

    pairwise = comp_data["pairwise_comparisons"][0]
    # The 4D guard MUST classify as not_directly_comparable because population and methodology differ!
    assert pairwise["relation"] == "not_directly_comparable"
    assert len(pairwise["differing_dimensions"]) >= 1
    assert "not directly comparable" in pairwise["explanation"].lower()

    # Reading priority ranking must be produced
    assert len(comp_data["reading_priority"]) == 2
    assert comp_data["reading_priority"][0]["rank"] == 1


@pytest.mark.asyncio
async def test_board_workflow_and_role_authorization(client):
    """
    Test propose -> approve -> reject -> undo workflow.
    Viewer role must be strictly rejected with 403 Forbidden on approve/reject/undo.
    """
    # 1. Register Owner (PI)
    owner_reg = await client.post("/api/v1/auth/register", json={
        "email": "pi_board@lab.org",
        "password": "Password123!",
        "full_name": "PI Board",
        "role": "owner"
    })
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Register Viewer (Student)
    viewer_reg = await client.post("/api/v1/auth/register", json={
        "email": "student_board@lab.org",
        "password": "Password123!",
        "full_name": "Student Board",
        "role": "viewer"
    })
    viewer_token = viewer_reg.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    col = (await client.post("/api/v1/collections", json={"name": "Evidence Board Collection"}, headers=owner_headers)).json()
    workspace_id = col["workspace_id"]

    doc_up = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Preference Optimization Stability"},
        files={"file": ("dpo.pdf", io.BytesIO(make_test_pdf("Direct preference optimization implicitly optimizes the reward function under the Bradley-Terry preference model.")), "application/pdf")},
        headers=owner_headers
    )
    doc = doc_up.json()["document"]

    # Grant permission to viewer for this document
    await client.post(f"/api/v1/documents/{doc['id']}/permissions", json={
        "user_email": "student_board@lab.org",
        "permission_level": "view"
    }, headers=owner_headers)

    # 3. Viewer proposes item
    prop_res = await client.post("/api/v1/board/propose", json={
        "workspace_id": workspace_id,
        "document_id": doc["id"],
        "title": "DPO avoids explicit reward models",
        "claim": "Direct preference optimization eliminates the need for an explicit reward model.",
        "citation_excerpt": "Direct preference optimization implicitly optimizes the reward function.",
        "page_number": 1,
        "evidence_status": "supported"
    }, headers=viewer_headers)
    assert prop_res.status_code == 200
    item = prop_res.json()
    assert item["board_status"] == "proposed"
    item_id = item["id"]

    # 4. Viewer attempts to approve -> MUST fail with 403 Forbidden!
    viewer_app = await client.put(f"/api/v1/board/{item_id}/approve", headers=viewer_headers)
    assert viewer_app.status_code == 403

    # 5. Owner approves -> 200 OK
    owner_app = await client.put(f"/api/v1/board/{item_id}/approve", headers=owner_headers)
    assert owner_app.status_code == 200
    assert owner_app.json()["board_status"] == "approved"

    # 6. Owner undoes decision -> Returns to proposed
    owner_undo = await client.post(f"/api/v1/board/{item_id}/undo", headers=owner_headers)
    assert owner_undo.status_code == 200
    assert owner_undo.json()["board_status"] == "proposed"

    # 7. Owner rejects -> Rejects with 200 OK
    owner_rej = await client.put(f"/api/v1/board/{item_id}/reject", headers=owner_headers)
    assert owner_rej.status_code == 200
    assert owner_rej.json()["board_status"] == "rejected"


@pytest.mark.asyncio
async def test_export_pre_retrieval_negative_authorization(client):
    """
    Negative authorization test:
    An unauthorized user must not be able to export evidence items derived from restricted documents.
    """
    # 1. Owner
    owner_reg = await client.post("/api/v1/auth/register", json={
        "email": "lead_export@secure.org",
        "password": "Password123!",
        "full_name": "Lead Export",
        "role": "owner"
    })
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Outsider (unauthorized)
    outsider_reg = await client.post("/api/v1/auth/register", json={
        "email": "outsider_export@ext.org",
        "password": "Password123!",
        "full_name": "Outsider Export",
        "role": "viewer"
    })
    outsider_token = outsider_reg.json()["access_token"]
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    col = (await client.post("/api/v1/collections", json={"name": "Restricted Oncology Papers"}, headers=owner_headers)).json()
    workspace_id = col["workspace_id"]

    doc_up = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Confidential Phase 3 Oncology Trial"},
        files={"file": ("trial.pdf", io.BytesIO(make_test_pdf("Primary endpoint demonstrated 89.2% overall survival rate in HER2-positive cohorts.")), "application/pdf")},
        headers=owner_headers
    )
    doc = doc_up.json()["document"]

    # Propose and approve evidence item
    prop = (await client.post("/api/v1/board/propose", json={
        "workspace_id": workspace_id,
        "document_id": doc["id"],
        "title": "Survival Rate Efficacy",
        "claim": "Primary endpoint achieved 89.2% overall survival rate.",
        "citation_excerpt": "Primary endpoint demonstrated 89.2% overall survival rate in HER2-positive cohorts.",
        "page_number": 1,
        "evidence_status": "supported"
    }, headers=owner_headers)).json()
    await client.put(f"/api/v1/board/{prop['id']}/approve", headers=owner_headers)

    # 3. Unauthorized user exports Markdown -> Must NOT contain restricted document or survival rate
    unauth_md = await client.get(f"/api/v1/board/export?workspace_id={workspace_id}&format=markdown&status=approved", headers=outsider_headers)
    assert unauth_md.status_code == 200
    assert "Confidential Phase 3" not in unauth_md.text
    assert "89.2%" not in unauth_md.text

    # 4. Unauthorized user exports CSV -> Must NOT leak restricted document
    unauth_csv = await client.get(f"/api/v1/board/export?workspace_id={workspace_id}&format=csv&status=approved", headers=outsider_headers)
    assert unauth_csv.status_code == 200
    assert "Confidential Phase 3" not in unauth_csv.text
    assert "89.2%" not in unauth_csv.text

    # 5. Owner exports Markdown -> Correctly contains approved item, citation, and page number
    owner_md = await client.get(f"/api/v1/board/export?workspace_id={workspace_id}&format=markdown&status=approved", headers=owner_headers)
    assert owner_md.status_code == 200
    assert "Confidential Phase 3" in owner_md.text
    assert "89.2%" in owner_md.text
    assert "Page 1" in owner_md.text

    # 6. Owner exports CSV -> Correctly contains structured columns
    owner_csv = await client.get(f"/api/v1/board/export?workspace_id={workspace_id}&format=csv&status=approved", headers=owner_headers)
    assert owner_csv.status_code == 200
    assert "Confidential Phase 3" in owner_csv.text
    assert "Survival Rate Efficacy" in owner_csv.text
