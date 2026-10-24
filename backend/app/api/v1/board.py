from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import get_current_user
from backend.app.services.board_service import BoardService
from backend.app.services.export_service import ExportService

router = APIRouter(prefix="/board", tags=["Evidence Board"])

class ProposeItemRequest(BaseModel):
    workspace_id: str
    document_id: str
    title: str
    claim: str
    citation_excerpt: Optional[str] = None
    page_number: Optional[int] = None
    evidence_status: str = "supported"

@router.get("")
async def list_board_items(
    workspace_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all evidence board items in the workspace visible to the user."""
    return await BoardService.list_board_items(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_role=current_user.role
    )

@router.post("/propose")
async def propose_board_item(
    payload: ProposeItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Propose a new item onto the evidence board."""
    return await BoardService.propose_item(
        db=db,
        workspace_id=payload.workspace_id,
        document_id=payload.document_id,
        title=payload.title,
        claim=payload.claim,
        citation_excerpt=payload.citation_excerpt,
        page_number=payload.page_number,
        evidence_status=payload.evidence_status,
        user_id=current_user.id,
        user_role=current_user.role
    )

@router.put("/{item_id}/approve")
async def approve_board_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a proposed item (reviewer/owner only)."""
    return await BoardService.approve_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        user_role=current_user.role
    )

@router.put("/{item_id}/reject")
async def reject_board_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject a proposed item (reviewer/owner only)."""
    return await BoardService.reject_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        user_role=current_user.role
    )

@router.post("/{item_id}/undo")
async def undo_board_item_decision(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Undo the last decision on an evidence item (reviewer/owner only)."""
    return await BoardService.undo_action(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        user_role=current_user.role
    )

@router.get("/export")
async def export_board(
    workspace_id: str = Query(...),
    format: str = Query("markdown", pattern="^(markdown|csv)$"),
    status: str = Query("approved"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export evidence items in Markdown or CSV format.
    Enforces pre-retrieval ACL: only exports items from documents the user is authorized to view.
    """
    res = await ExportService.export_board(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_role=current_user.role,
        export_format=format,
        status_filter=status
    )
    return Response(
        content=res["content"],
        media_type=res["media_type"],
        headers={"Content-Disposition": f"attachment; filename={res['filename']}"}
    )
