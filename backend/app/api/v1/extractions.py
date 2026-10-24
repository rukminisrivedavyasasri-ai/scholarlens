from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from backend.app.database import get_db
from backend.app.services.auth_service import get_current_user
from backend.app.models.user import User
from backend.app.models.extraction import ExtractedDetail
from backend.app.services.acl_service import check_document_access, ROLE_HIERARCHY
from backend.app.services.extraction_service import extraction_service
from backend.app.services.claim_verification_service import claim_verification_service
from backend.app.services.audit_service import log_audit_event
from backend.app.schemas.extraction import (
    ExtractionResponse,
    ExtractionUpdateRequest,
    ClaimVerifyRequest,
    ClaimVerifyResponse
)

router = APIRouter(prefix="", tags=["extractions-and-verification"])

@router.get("/documents/{document_id}/extractions", response_model=List[ExtractionResponse])
async def get_document_extractions(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the 5-field structured study details for a document.
    Enforces server-side ACL before reading extracted data.
    """
    await check_document_access(db, current_user.id, document_id, required_level="view")

    stmt = select(ExtractedDetail).where(ExtractedDetail.document_id == document_id)
    res = await db.execute(stmt)
    records = res.scalars().all()
    return [ExtractionResponse.model_validate(r) for r in records]

@router.post("/documents/{document_id}/extractions/extract", response_model=List[ExtractionResponse])
async def trigger_document_extraction(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Runs automated 5-field study details extraction over document chunks.
    Missing fields are stored explicitly as 'unavailable' with zero hallucination.
    """
    records = await extraction_service.extract_study_details(db, current_user.id, document_id)

    await log_audit_event(
        db=db,
        action_type="EXTRACTION_RUN",
        user_id=current_user.id,
        resource_id=document_id,
        details={"fields_extracted": len(records)},
        ip_address=request.client.host if request.client else None
    )

    return [ExtractionResponse.model_validate(r) for r in records]

@router.put("/documents/{document_id}/extractions/{extraction_id}", response_model=ExtractionResponse)
async def update_extraction_review(
    document_id: str,
    extraction_id: str,
    update_data: ExtractionUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Human review control: Edit and approve/reject an extracted study field.
    Requires role 'reviewer' or 'owner'. Viewers receive 403 Forbidden.
    """
    # 1. Document access
    await check_document_access(db, current_user.id, document_id, required_level="view")

    # 2. Strict Role Hierarchy check: viewer cannot approve/edit extractions
    user_level = ROLE_HIERARCHY.get(current_user.role, 0)
    if user_level < ROLE_HIERARCHY.get("reviewer", 2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Reviewer or Owner role required to approve or edit extractions."
        )

    # 3. Fetch record
    stmt = select(ExtractedDetail).where(
        ExtractedDetail.id == extraction_id,
        ExtractedDetail.document_id == document_id
    )
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction record not found.")

    if update_data.field_value is not None:
        record.field_value = update_data.field_value
        record.is_unavailable = False

    record.review_status = update_data.review_status
    record.reviewed_by = current_user.id
    record.reviewed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(record)

    await log_audit_event(
        db=db,
        action_type="EXTRACTION_REVIEW",
        user_id=current_user.id,
        resource_id=extraction_id,
        details={
            "field_name": record.field_name,
            "status": record.review_status,
            "document_id": document_id
        },
        ip_address=request.client.host if request.client else None
    )

    return ExtractionResponse.model_validate(record)

@router.post("/qa/verify-claim", response_model=ClaimVerifyResponse)
async def verify_claim_endpoint(
    verify_req: ClaimVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs claim-level entailment verification against cited passage and validates citation boundaries.
    """
    result = await claim_verification_service.verify_claim(
        db=db,
        user_id=current_user.id,
        claim_text=verify_req.claim_text,
        document_id=verify_req.document_id,
        page_number=verify_req.page_number,
        cited_excerpt=verify_req.cited_excerpt
    )
    return ClaimVerifyResponse(**result)
