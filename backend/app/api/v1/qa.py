from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.app.database import get_db
from backend.app.services.auth_service import get_current_user
from backend.app.models.user import User
from backend.app.schemas.qa import (
    SemanticSearchRequest,
    PassageResult,
    QARequest,
    QAResponse
)
from backend.app.services.retrieval_service import retrieval_service
from backend.app.services.qa_service import qa_service
from backend.app.services.audit_service import log_audit_event

router = APIRouter(prefix="", tags=["search-and-qa"])

@router.post("/search/semantic", response_model=List[PassageResult])
async def search_passages(
    search_req: SemanticSearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs semantic vector search across document passages.
    MANDATORY PRE-RETRIEVAL AUTHORIZATION: The vector query strictly filters
    by permitted document IDs before ranking. Restricted documents are never searched.
    """
    passages = await retrieval_service.retrieve_passages(
        db=db,
        user_id=current_user.id,
        query=search_req.query,
        collection_id=search_req.collection_id,
        top_k=search_req.top_k
    )

    await log_audit_event(
        db=db,
        action_type="SEARCH_SEMANTIC",
        user_id=current_user.id,
        details={
            "query": search_req.query,
            "collection_id": search_req.collection_id,
            "passages_retrieved": len(passages)
        },
        ip_address=request.client.host if request.client else None
    )

    return [PassageResult(**p) for p in passages]

@router.post("/qa/query", response_model=QAResponse)
async def grounded_qa(
    qa_req: QARequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Grounded Q&A with inline citations [doc, page] and prompt-injection defense.
    - Pre-retrieval authorization enforced inside database vector query.
    - Retrieved passages wrapped in untrusted data delimiters.
    - Zero-hallucination policy: abstains if evidence is absent.
    - Mode toggle: 'grounded_verified' vs 'baseline_rag'.
    """
    passages = await retrieval_service.retrieve_passages(
        db=db,
        user_id=current_user.id,
        query=qa_req.query,
        collection_id=qa_req.collection_id,
        top_k=5
    )

    result = qa_service.synthesize_grounded_answer(
        query=qa_req.query,
        passages=passages,
        mode=qa_req.mode
    )

    await log_audit_event(
        db=db,
        action_type="QA_QUERY",
        user_id=current_user.id,
        details={
            "query": qa_req.query,
            "mode": qa_req.mode,
            "passages_used": len(passages),
            "abstention": result.get("abstention", False)
        },
        ip_address=request.client.host if request.client else None
    )

    return QAResponse(**result)
