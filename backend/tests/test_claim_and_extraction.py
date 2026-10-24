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
async def test_claim_verification_entailment(client):
    """
    Verifies claim-level entailment classification:
    - Supported: factual assertions and numbers match source text.
    - Partially supported: claim requires qualification or subgroup condition.
    - Unsupported: claim is uncorroborated by passage.
    - Invalid citation: page number out of bounds flags unsupported.
    """
    # 1. Register Alice
    reg = await client.post("/api/v1/auth/register", json={
        "email": "dr_alice_nli@lab.edu",
        "password": "Password123!",
        "full_name": "Dr. Alice NLI",
        "role": "owner"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create collection & upload document
    col = (await client.post("/api/v1/collections", json={"name": "NLI Verification Set"}, headers=headers)).json()
    
    passage_text = (
        "In the multicenter randomized trial, participants randomized to adaptive closed-loop protocol "
        "achieved 92.4% retention at week 12 compared to 78.1% in static controls. "
        "Secondary fatigue was reduced solely in the severe baseline fatigue subgroup. "
        "Adverse events such as headaches were unrecorded in the protocol."
    )
    pdf_content = make_test_pdf(passage_text)

    up_res = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Closed Loop Cognitive Trial"},
        files={"file": ("trial.pdf", io.BytesIO(pdf_content), "application/pdf")},
        headers=headers
    )
    assert up_res.status_code == 200
    doc_id = up_res.json()["document"]["id"]

    # 3. Test Supported Claim
    sup_res = await client.post("/api/v1/qa/verify-claim", json={
        "claim_text": "Adaptive closed-loop intervention achieved 92.4% retention at week 12 versus 78.1% in controls.",
        "document_id": doc_id,
        "page_number": 1
    }, headers=headers)
    assert sup_res.status_code == 200
    sup_data = sup_res.json()
    assert sup_data["status"] == "supported"
    assert sup_data["valid_citation"] is True
    assert sup_data["confidence"] >= 0.85

    # 4. Test Partially Supported Claim (Missing subgroup qualification)
    part_res = await client.post("/api/v1/qa/verify-claim", json={
        "claim_text": "Secondary fatigue decreased universally across the entire cohort without qualification.",
        "document_id": doc_id,
        "page_number": 1
    }, headers=headers)
    assert part_res.status_code == 200
    part_data = part_res.json()
    assert part_data["status"] in ["partially_supported", "unsupported"]

    # 5. Test Unsupported Claim (Fabrication)
    unsup_res = await client.post("/api/v1/qa/verify-claim", json={
        "claim_text": "The protocol eliminated migraine headaches completely in 100% of participants.",
        "document_id": doc_id,
        "page_number": 1
    }, headers=headers)
    assert unsup_res.status_code == 200
    unsup_data = unsup_res.json()
    assert unsup_data["status"] == "unsupported"

    # 6. Test Invalid Citation (Out of bounds page 999)
    bounds_res = await client.post("/api/v1/qa/verify-claim", json={
        "claim_text": "Adaptive closed-loop achieved 92.4% retention.",
        "document_id": doc_id,
        "page_number": 999
    }, headers=headers)
    assert bounds_res.status_code == 200
    bounds_data = bounds_res.json()
    assert bounds_data["status"] == "unsupported"
    assert bounds_data["valid_citation"] is False
    assert "out of bounds" in bounds_data["reasoning"].lower()

@pytest.mark.asyncio
async def test_structured_extraction_and_zero_hallucination(client):
    """
    Verifies that the 5 core study fields (objective, methodology, population, findings, limitations)
    are extracted with citations and missing fields are explicitly flagged as 'unavailable'.
    """
    reg = await client.post("/api/v1/auth/register", json={
        "email": "dr_extract@lab.edu",
        "password": "Password123!",
        "full_name": "Dr. Extract",
        "role": "owner"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    col = (await client.post("/api/v1/collections", json={"name": "Extraction Collection"}, headers=headers)).json()

    paper_text = (
        "Primary Objective: The study objective is to evaluate 12-week adherence to closed-loop cognitive protocols. "
        "Methodology: We conducted a multicenter double-blind randomized controlled trial. "
        "Participants Cohort: The target population included 480 patients aged 18 to 65 with mild impairment. "
        "Findings and Results: Participants achieved 92.4% retention in adaptive vs 78.1% in static controls."
    )
    pdf_content = make_test_pdf(paper_text)

    up_res = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Cognitive Protocol Study"},
        files={"file": ("cog.pdf", io.BytesIO(pdf_content), "application/pdf")},
        headers=headers
    )
    assert up_res.status_code == 200
    doc_id = up_res.json()["document"]["id"]

    # Trigger extraction
    ext_res = await client.post(f"/api/v1/documents/{doc_id}/extractions/extract", headers=headers)
    assert ext_res.status_code == 200
    fields = ext_res.json()
    assert len(fields) == 5

    field_map = {f["field_name"]: f for f in fields}
    assert "objective" in field_map
    assert "methodology" in field_map
    assert "population" in field_map
    assert "findings" in field_map
    assert "limitations" in field_map

    # Findings should be extracted with page number
    assert field_map["findings"]["is_unavailable"] is False
    assert field_map["findings"]["page_number"] == 1
    assert "92.4%" in field_map["findings"]["field_value"]

    # Objective should be extracted
    assert field_map["objective"]["is_unavailable"] is False
    assert "adherence" in field_map["objective"]["field_value"].lower()

    # Limitations was NOT in the text -> MUST be explicitly marked 'unavailable'
    assert field_map["limitations"]["is_unavailable"] is True
    assert field_map["limitations"]["field_value"] == "unavailable"
    assert "limitations" in field_map["limitations"]["unavailable_reason"].lower() or "explicitly" in field_map["limitations"]["unavailable_reason"].lower()

@pytest.mark.asyncio
async def test_negative_extraction_acl_and_role_boundaries(client):
    """
    CRITICAL SECURITY TEST:
    1. Unauthorized user receives 403 Forbidden when requesting extractions.
    2. Viewer role receives 403 Forbidden when attempting to edit/approve extractions (Reviewer/Owner required).
    3. Reviewer/Owner role can approve extraction (200 OK).
    """
    # 1. Alice (Owner)
    alice = (await client.post("/api/v1/auth/register", json={
        "email": "alice_lead@lab.edu",
        "password": "Password123!",
        "full_name": "Alice Lead",
        "role": "owner"
    })).json()
    alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}

    # 2. Bob (External unauthorized user)
    bob = (await client.post("/api/v1/auth/register", json={
        "email": "bob_unauth@outsider.com",
        "password": "Password123!",
        "full_name": "Bob Outsider",
        "role": "viewer"
    })).json()
    bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}

    col = (await client.post("/api/v1/collections", json={"name": "Alice Research"}, headers=alice_headers)).json()

    pdf_content = make_test_pdf("Primary Objective: Quantify trial retention. Findings: 88% retention rate achieved.")
    up = await client.post(
        "/api/v1/documents/upload",
        data={"collection_id": col["id"], "title": "Confidential Extraction Doc"},
        files={"file": ("trial.pdf", io.BytesIO(pdf_content), "application/pdf")},
        headers=alice_headers
    )
    doc_id = up.json()["document"]["id"]

    # Alice triggers extraction
    ext_list = (await client.post(f"/api/v1/documents/{doc_id}/extractions/extract", headers=alice_headers)).json()
    ext_id = ext_list[0]["id"]

    # Bob attempts to view extractions -> MUST be 403 Forbidden
    bob_view = await client.get(f"/api/v1/documents/{doc_id}/extractions", headers=bob_headers)
    assert bob_view.status_code == 403, "Bob must not view extractions for restricted document!"

    # Bob attempts to approve extraction -> MUST be 403 Forbidden
    bob_approve = await client.put(
        f"/api/v1/documents/{doc_id}/extractions/{ext_id}",
        json={"review_status": "approved"},
        headers=bob_headers
    )
    assert bob_approve.status_code == 403

    # Alice (Owner) approves extraction -> 200 OK
    alice_approve = await client.put(
        f"/api/v1/documents/{doc_id}/extractions/{ext_id}",
        json={"review_status": "approved", "field_value": "Formally verified objective: Quantify trial retention."},
        headers=alice_headers
    )
    assert alice_approve.status_code == 200
    assert alice_approve.json()["review_status"] == "approved"
    assert alice_approve.json()["field_value"] == "Formally verified objective: Quantify trial retention."
