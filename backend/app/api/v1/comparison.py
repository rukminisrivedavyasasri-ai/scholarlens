from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import get_current_user
from backend.app.services.comparison_service import ComparisonService

router = APIRouter(prefix="/comparison", tags=["Comparison"])

class ComparisonRequest(BaseModel):
    question: str
    document_ids: List[str]

@router.post("/matrix")
async def generate_comparison_matrix(
    request: ComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a study-by-study comparison matrix for a research question across up to 5 documents.
    Enforces the 4-Dimension Comparability Guard (Population, Setting, Method, Outcome Measure).
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="At least one document ID must be provided.")

    return await ComparisonService.compare_studies(
        db=db,
        question=request.question,
        document_ids=request.document_ids,
        user_id=current_user.id,
        user_role=current_user.role
    )
